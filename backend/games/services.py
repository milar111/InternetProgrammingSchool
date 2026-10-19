import random
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .map import (
    BULGARIA_MAP_ADJACENCY,
    BULGARIA_MAP_TERRITORIES,
    find_all_independent_triplets,
    validate_game_map,
    validate_map_definition,
)
from .models import Capital, Game, GamePlayer, Territory

ALLOWED_PLAYER_COLORS = ("red", "green", "blue")


class GameInitializationError(Exception):
    """Base exception for all game initialization errors."""
    pass


class GameNotFoundError(GameInitializationError):
    """Raised when the specified game does not exist."""
    pass


class InvalidGameStatusError(GameInitializationError):
    """Raised when the game is not in 'waiting' status."""
    pass


class InvalidPlayersError(GameInitializationError):
    """Raised when the game does not have exactly 3 valid players."""
    pass


class ExistingGameStateError(GameInitializationError):
    """Raised when territories or capitals already exist for the game."""
    pass


class InvalidMapDefinitionError(GameInitializationError):
    """Raised when the project map definition fails M04 validation."""
    pass


class NoValidCapitalsError(GameInitializationError):
    """Raised when no mutually non-adjacent triplet of capitals can be found."""
    pass


def initialize_game(game_or_id, *, seed=None, capital_triplet=None):
    """
    Initializes a game from waiting to active status as a single atomic operation:
    1. Validates preconditions (status == waiting, 3 valid players, no existing territories/capitals, valid map).
    2. Randomly selects a mutually non-adjacent triplet of capitals and assigns them to the 3 players.
    3. Creates N territories and their symmetrical neighbor relations.
    4. Creates 3 capitals with health=3 on the chosen territories with territory.owner = player.
    5. Sets remaining N-3 territories with owner = None and score = 0.
    6. Transitions game.status from 'waiting' to 'active' as a single atomic transaction.
    """
    if isinstance(game_or_id, Game):
        game_id = game_or_id.pk
    else:
        try:
            game_id = int(game_or_id)
        except (ValueError, TypeError):
            raise GameNotFoundError(f"Invalid game ID: {game_or_id}")

    with transaction.atomic():
        try:
            game = Game.objects.select_for_update().get(pk=game_id)
        except Game.DoesNotExist:
            raise GameNotFoundError(f"Game #{game_id} does not exist.")

        # 1. Game must be in waiting status
        if game.status != Game.WAITING:
            raise InvalidGameStatusError(
                f"Game #{game.id} is in '{game.status}' status. Only games in '{Game.WAITING}' status can be initialized."
            )

        # 2. Game must not have existing territories or capitals
        if game.territories.exists():
            raise ExistingGameStateError(
                f"Game #{game.id} already has territories created. Partial or existing states cannot be re-initialized."
            )

        if Capital.objects.filter(territory__game=game).exists():
            raise ExistingGameStateError(
                f"Game #{game.id} already has capitals created."
            )

        # 3. Exactly 3 valid players
        players = list(game.players.select_for_update().order_by("player_order"))
        if len(players) != 3:
            raise InvalidPlayersError(
                f"Game #{game.id} must have exactly 3 players to initialize, found {len(players)}."
            )

        # Distinct users
        user_ids = {p.user_id for p in players}
        if len(user_ids) != 3:
            raise InvalidPlayersError("Game players must be 3 distinct users.")

        # Non-negative scores
        for p in players:
            if p.score < 0:
                raise InvalidPlayersError(
                    f"Player '{p.user.username}' has negative score ({p.score}). All player scores must be non-negative."
                )

        # Allowed and distinct colors
        colors = [p.color.strip().lower() for p in players]
        for idx, color in enumerate(colors):
            if not color or color not in ALLOWED_PLAYER_COLORS:
                raise InvalidPlayersError(
                    f"Player '{players[idx].user.username}' has invalid color '{players[idx].color}'. Allowed colors: {sorted(ALLOWED_PLAYER_COLORS)}."
                )
        if len(set(colors)) != 3:
            raise InvalidPlayersError("All 3 players must have distinct colors.")

        # Check players do not already have capitals assigned
        if Capital.objects.filter(player__in=players).exists():
            raise ExistingGameStateError("One or more players already have a capital assigned.")

        # 4. Map definition validation
        try:
            validate_map_definition()
        except ValidationError as e:
            raise InvalidMapDefinitionError(f"Map definition is invalid: {e}")

        # 5. Independent triplet selection
        triplets = find_all_independent_triplets(BULGARIA_MAP_ADJACENCY)
        if not triplets:
            raise NoValidCapitalsError("No mutually non-adjacent triplet of territories exists on the map.")

        if capital_triplet is not None:
            norm_triplet = tuple(sorted(s.strip().lower() for s in capital_triplet))
            valid_normalized = {tuple(sorted(t)) for t in triplets}
            if norm_triplet not in valid_normalized:
                raise NoValidCapitalsError(
                    f"Provided capital triplet {capital_triplet} is not a valid mutually non-adjacent triplet."
                )
            chosen_triplet = list(capital_triplet)
        else:
            rng = random.Random(seed) if seed is not None else random
            chosen_triplet = list(rng.choice(triplets))
            # Randomly shuffle triplet so input player order does not determine territory
            rng.shuffle(chosen_triplet)

        # Map each player to their capital territory slug
        capital_assignment = dict(zip(players, chosen_triplet))

        # 6. Create territories
        territory_map = {}
        for t_def in BULGARIA_MAP_TERRITORIES:
            slug = t_def["slug"]
            name = t_def["name"]

            # Owner is set only for capital territories
            owner = None
            for p, cap_slug in capital_assignment.items():
                if cap_slug == slug:
                    owner = p
                    break

            territory = Territory.objects.create(
                game=game,
                name=name,
                slug=slug,
                owner=owner,
                score=0,
            )
            territory_map[slug] = territory

        # 7. Create symmetrical neighbor relationships
        for slug, neighbor_slugs in BULGARIA_MAP_ADJACENCY.items():
            territory = territory_map[slug]
            neighbor_objs = [territory_map[n_slug] for n_slug in neighbor_slugs]
            territory.neighbors.add(*neighbor_objs)

        # 8. Create Capitals (health=3)
        for player, cap_slug in capital_assignment.items():
            cap_territory = territory_map[cap_slug]
            Capital.objects.create(
                territory=cap_territory,
                player=player,
                health=3,
            )

        # 9. Transition game status to active
        game.status = Game.ACTIVE
        game.started_at = timezone.now()
        game.save(update_fields=["status", "started_at"])

        # 10. Verify game map integrity
        validate_game_map(game)

        if isinstance(game_or_id, Game):
            game_or_id.refresh_from_db()

        return game
