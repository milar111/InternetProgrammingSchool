from django.core.exceptions import ValidationError
from django.db import models, transaction

from .models import Game, GamePlayer, Round, Territory, TerritoryCapture, TerritorySelectionRight


class CaptureServiceError(Exception):
    """Base exception for all capture and scoring service operations."""
    pass


class TerritoryNotAdjacentError(CaptureServiceError):
    """Raised when the selected territory is not adjacent to player's holdings (and exception does not apply)."""
    pass


class TerritoryAlreadyOwnedError(CaptureServiceError):
    """Raised when attempting to choose an already owned territory."""
    pass


class NoSelectionRightsError(CaptureServiceError):
    """Raised when a player attempts to choose without selection rights."""
    pass


class OutOfTurnSelectionError(CaptureServiceError):
    """Raised when a player attempts to choose before their turn or over the allocated limit."""
    pass


class NoFreeTerritoriesError(CaptureServiceError):
    """Raised when trying to create a city_capture round but all territories are captured."""
    pass


class PendingSelectionRightsError(CaptureServiceError):
    """Raised when trying to create a new round while pending selection rights remain."""
    pass


# Scoring constants for System 1 (Chosen system)
WIN_REWARD = 200
CAPTURE_REWARD = 100
TERRITORY_SCORE_INCREMENT = 100


def _resolve_territory(territory_or_id):
    if isinstance(territory_or_id, Territory):
        territory_or_id.refresh_from_db()
        return territory_or_id
    try:
        return Territory.objects.get(pk=int(territory_or_id))
    except (Territory.DoesNotExist, ValueError, TypeError):
        raise CaptureServiceError(f"Territory '{territory_or_id}' does not exist.")


def get_eligible_territories(game, player):
    """
    Returns QuerySet of territories eligible for player to capture:
    - Must be free (owner=None) in the specified game.
    - Must be adjacent to at least one of player's owned territories (including capital).
    - Exception rule: if player has NO free adjacent neighbors, they can pick ANY free territory in game.
    """
    free_territories = game.territories.filter(owner__isnull=True)
    if not free_territories.exists():
        return free_territories.none()

    player_holdings = player.territories.all()
    if not player_holdings.exists():
        return free_territories

    # Find free neighbors adjacent to player's holdings
    free_neighbors = free_territories.filter(neighbors__owner=player).distinct()

    if free_neighbors.exists():
        return free_neighbors

    # Exception rule: isolated player with no adjacent free neighbors can pick any free territory
    return free_territories


def choose_territory(game_or_id, player_or_id, territory_or_id):
    """
    Executes a territory selection by player in an active game:
    - Validates game is active.
    - Validates player has the active turn from the latest completed city_capture round.
    - Validates territory is free, belongs to game, and is eligible (adjacent or exception).
    - Atomically:
        1. Changes territory.owner to player.
        2. Increases territory.score by 100.
        3. Awards player.score by 100.
        4. Increments right.used_choices by 1.
        5. Records TerritoryCapture log.
    """
    from .round_services import _resolve_game, _resolve_player, InvalidGameStateError, PlayerNotEligibleError

    game = _resolve_game(game_or_id)
    player = _resolve_player(player_or_id)
    territory = _resolve_territory(territory_or_id)

    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game.pk)
        if game.status != Game.ACTIVE:
            raise InvalidGameStateError("Game must be active to choose territories.")

        if player.game_id != game.id:
            raise PlayerNotEligibleError("Player does not belong to this game.")

        if territory.game_id != game.id:
            raise CaptureServiceError("Territory does not belong to this game.")

        latest_round = game.rounds.filter(status=Round.COMPLETED).order_by("-number").first()
        if not latest_round:
            raise NoSelectionRightsError("No completed round exists in this game to provide selection rights.")

        # Find active grant with remaining choices
        active_grant = (
            latest_round.selection_rights.select_for_update()
            .filter(used_choices__lt=models.F("allocated_choices"))
            .order_by("order")
            .first()
        )

        if not active_grant:
            raise NoSelectionRightsError("All territory selection rights for this round have been used.")

        if active_grant.player_id != player.id:
            has_later = latest_round.selection_rights.filter(player=player, order__gt=active_grant.order).exists()
            if has_later:
                raise OutOfTurnSelectionError(
                    f"It is not {player.user.username}'s turn to choose yet (waiting for earlier player)."
                )
            raise NoSelectionRightsError(f"Player {player.user.username} has no remaining selection rights.")

        # Lock territory and check ownership
        territory = Territory.objects.select_for_update().get(pk=territory.pk)
        if territory.owner_id is not None:
            raise TerritoryAlreadyOwnedError(
                f"Territory '{territory.name}' is already owned by {territory.owner.user.username}."
            )

        # Check eligibility (adjacency or exception)
        eligible = get_eligible_territories(game, player)
        if not eligible.filter(pk=territory.pk).exists():
            raise TerritoryNotAdjacentError(
                f"Territory '{territory.name}' is not adjacent to any territory owned by {player.user.username}."
            )

        # Apply scoring and state changes atomically
        score_before = territory.score
        territory.score += TERRITORY_SCORE_INCREMENT
        score_after = territory.score
        territory.owner = player
        territory.save(update_fields=["owner", "score"])

        player = GamePlayer.objects.select_for_update().get(pk=player.pk)
        player.score += CAPTURE_REWARD
        player.save(update_fields=["score"])

        active_grant.used_choices += 1
        active_grant.save(update_fields=["used_choices"])

        capture = TerritoryCapture.objects.create(
            round=latest_round,
            player=player,
            territory=territory,
            choice_number=active_grant.used_choices,
            points_awarded=CAPTURE_REWARD,
            territory_score_before=score_before,
            territory_score_after=score_after,
        )

        if isinstance(territory_or_id, Territory):
            territory_or_id.refresh_from_db()
        if isinstance(player_or_id, GamePlayer):
            player_or_id.refresh_from_db()

        return capture


def get_selection_status(game_or_id):
    """
    Returns current selection status and remaining rights for the game:
    - active_round_id, current_player, remaining_choices, eligible_territories, free_territories_count
    """
    from .round_services import _resolve_game
    game = _resolve_game(game_or_id)

    free_count = game.territories.filter(owner__isnull=True).count()
    latest_round = game.rounds.filter(status=Round.COMPLETED).order_by("-number").first()

    current_player_name = None
    remaining_choices = 0
    eligible_territories = []

    if latest_round:
        active_grant = (
            latest_round.selection_rights.filter(used_choices__lt=models.F("allocated_choices"))
            .order_by("order")
            .first()
        )
        if active_grant:
            current_player_name = active_grant.player.user.username
            remaining_choices = active_grant.remaining_choices
            eligible_qs = get_eligible_territories(game, active_grant.player)
            eligible_territories = list(eligible_qs.values_list("slug", flat=True))

    return {
        "latest_round_id": latest_round.id if latest_round else None,
        "current_player": current_player_name,
        "remaining_choices": remaining_choices,
        "eligible_territories": eligible_territories,
        "free_territories_count": free_count,
        "phase_completed": (free_count == 0),
    }
