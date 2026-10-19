from unittest.mock import patch
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from games.admin import GameAdmin, GamePlayerAdmin, GamePlayerInline
from games.map import (
    BULGARIA_MAP_ADJACENCY,
    BULGARIA_MAP_TERRITORIES,
    find_all_independent_triplets,
    validate_game_map,
)
from games.models import Capital, Game, GamePlayer, Round, Territory
from games.services import (
    ExistingGameStateError,
    GameNotFoundError,
    InvalidGameStatusError,
    InvalidMapDefinitionError,
    InvalidPlayersError,
    NoValidCapitalsError,
    initialize_game,
)
from questions.models import Category, NumericQuestion

User = get_user_model()


class GameInitializationTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", email="host@example.com", password="pwd")
        self.u1 = User.objects.create_user(username="player1", email="p1@example.com", password="pwd")
        self.u2 = User.objects.create_user(username="player2", email="p2@example.com", password="pwd")
        self.u3 = User.objects.create_user(username="player3", email="p3@example.com", password="pwd")

        self.game = Game.objects.create(created_by=self.host)
        self.p1 = GamePlayer.objects.create(game=self.game, user=self.u1, player_order=1, color="red", score=0)
        self.p2 = GamePlayer.objects.create(game=self.game, user=self.u2, player_order=2, color="green", score=0)
        self.p3 = GamePlayer.objects.create(game=self.game, user=self.u3, player_order=3, color="blue", score=0)

    def test_successful_initialization_full_state(self):
        """Tests that a successful initialization creates the exact expected M05 state."""
        game = initialize_game(self.game)

        # 1. Game status and timestamps
        self.assertEqual(game.status, Game.ACTIVE)
        self.assertIsNotNone(game.started_at)
        self.assertIsNone(game.finished_at)

        # 2. Exactly N (15) territories
        territories = list(game.territories.all())
        self.assertEqual(len(territories), len(BULGARIA_MAP_TERRITORIES))
        self.assertEqual(len(territories), 15)

        expected_slugs = {t["slug"] for t in BULGARIA_MAP_TERRITORIES}
        expected_names = {t["slug"]: t["name"] for t in BULGARIA_MAP_TERRITORIES}
        actual_slugs = {t.slug for t in territories}
        self.assertEqual(actual_slugs, expected_slugs)

        for t in territories:
            self.assertEqual(t.name, expected_names[t.slug])
            self.assertEqual(t.score, 0)
            self.assertEqual(t.game_id, game.id)

        # 3. Adjacency graph is symmetric and matches M04
        for t in territories:
            actual_neighbors = set(t.neighbors.values_list("slug", flat=True))
            expected_neighbors = set(BULGARIA_MAP_ADJACENCY[t.slug])
            self.assertEqual(actual_neighbors, expected_neighbors)
            for n in t.neighbors.all():
                self.assertEqual(n.game_id, game.id)

        # 4. Exactly 3 capitals on mutually non-adjacent territories
        capitals = list(Capital.objects.filter(territory__game=game))
        self.assertEqual(len(capitals), 3)

        capital_players = {c.player_id for c in capitals}
        expected_players = {self.p1.id, self.p2.id, self.p3.id}
        self.assertEqual(capital_players, expected_players)

        capital_slugs = [c.territory.slug for c in capitals]
        self.assertEqual(len(capital_slugs), 3)
        # Verify mutual non-adjacency
        for i in range(len(capital_slugs)):
            for j in range(i + 1, len(capital_slugs)):
                a, b = capital_slugs[i], capital_slugs[j]
                self.assertNotIn(b, BULGARIA_MAP_ADJACENCY[a])
                self.assertNotIn(a, BULGARIA_MAP_ADJACENCY[b])

        # 5. Capital health = 3 and territory owner is set
        for c in capitals:
            self.assertEqual(c.health, 3)
            self.assertEqual(c.territory.owner_id, c.player_id)
            self.assertEqual(c.territory.score, 0)

        # 6. Remaining N-3 (12) territories have owner = None
        non_capital_territories = game.territories.filter(capital__isnull=True)
        self.assertEqual(non_capital_territories.count(), 12)
        for t in non_capital_territories:
            self.assertIsNone(t.owner)
            self.assertEqual(t.score, 0)

        # 7. Players records are preserved
        players = list(game.players.order_by("player_order"))
        self.assertEqual(len(players), 3)
        self.assertEqual(players[0].user, self.u1)
        self.assertEqual(players[0].color, "red")
        self.assertEqual(players[0].score, 0)
        self.assertEqual(players[1].user, self.u2)
        self.assertEqual(players[1].color, "green")
        self.assertEqual(players[1].score, 0)
        self.assertEqual(players[2].user, self.u3)
        self.assertEqual(players[2].color, "blue")
        self.assertEqual(players[2].score, 0)

        # 8. validate_game_map returns True
        self.assertTrue(validate_game_map(game))

    def test_initialization_via_model_method(self):
        """Tests that game.initialize() works and updates instance in-place."""
        result = self.game.initialize(seed=42)
        self.assertEqual(result.id, self.game.id)
        self.assertEqual(self.game.status, Game.ACTIVE)
        self.assertIsNotNone(self.game.started_at)
        self.assertEqual(self.game.territories.count(), 15)

    def test_initialization_with_game_id_string_or_int(self):
        """Tests that passing integer or string game_id works."""
        game = initialize_game(self.game.id)
        self.assertEqual(game.status, Game.ACTIVE)

        game2 = Game.objects.create(created_by=self.host)
        GamePlayer.objects.create(game=game2, user=self.u1, player_order=1, color="red")
        GamePlayer.objects.create(game=game2, user=self.u2, player_order=2, color="green")
        GamePlayer.objects.create(game=game2, user=self.u3, player_order=3, color="blue")
        game2_init = initialize_game(str(game2.id))
        self.assertEqual(game2_init.status, Game.ACTIVE)

    def test_deterministic_seed(self):
        """Tests that passing seed produces reproducible capital assignments."""
        game2 = Game.objects.create(created_by=self.host)
        GamePlayer.objects.create(game=game2, user=self.u1, player_order=1, color="red")
        GamePlayer.objects.create(game=game2, user=self.u2, player_order=2, color="green")
        GamePlayer.objects.create(game=game2, user=self.u3, player_order=3, color="blue")

        initialize_game(self.game, seed=999)
        initialize_game(game2, seed=999)

        caps1 = {
            c.player.player_order: c.territory.slug for c in Capital.objects.filter(territory__game=self.game)
        }
        caps2 = {
            c.player.player_order: c.territory.slug for c in Capital.objects.filter(territory__game=game2)
        }
        self.assertEqual(caps1, caps2)

    def test_explicit_valid_capital_triplet(self):
        """Tests that passing a valid capital triplet assigns those exact territories."""
        triplet = ("vidin", "varna", "blagoevgrad")
        initialize_game(self.game, capital_triplet=triplet)

        assigned_slugs = set(Capital.objects.filter(territory__game=self.game).values_list("territory__slug", flat=True))
        self.assertEqual(assigned_slugs, set(triplet))

    def test_explicit_invalid_adjacent_capital_triplet_rejected(self):
        """Tests that passing an adjacent triplet raises NoValidCapitalsError."""
        adjacent_triplet = ("sofia", "blagoevgrad", "varna")
        with self.assertRaises(NoValidCapitalsError):
            initialize_game(self.game, capital_triplet=adjacent_triplet)

    def test_reject_nonexistent_game(self):
        """Tests that attempting to initialize a non-existent game raises GameNotFoundError."""
        with self.assertRaises(GameNotFoundError):
            initialize_game(999999)

    def test_reject_invalid_game_id_type(self):
        """Tests that invalid id raises GameNotFoundError."""
        with self.assertRaises(GameNotFoundError):
            initialize_game("not-a-number")

    def test_reject_already_active_game(self):
        """Tests that an active game cannot be re-initialized."""
        initialize_game(self.game)
        with self.assertRaises(InvalidGameStatusError):
            initialize_game(self.game)

    def test_reject_finished_game(self):
        """Tests that a finished game cannot be initialized."""
        self.game.status = Game.FINISHED
        self.game.save()
        with self.assertRaises(InvalidGameStatusError):
            initialize_game(self.game)

    def test_reject_cancelled_game(self):
        """Tests that a cancelled game cannot be initialized."""
        self.game.status = Game.CANCELLED
        self.game.save()
        with self.assertRaises(InvalidGameStatusError):
            initialize_game(self.game)

    def test_reject_less_than_3_players(self):
        """Tests that games with 0, 1, or 2 players cannot be initialized."""
        self.p3.delete()
        self.assertEqual(self.game.players.count(), 2)
        with self.assertRaises(InvalidPlayersError):
            initialize_game(self.game)

    def test_reject_more_than_3_players(self):
        """Tests that games with more than 3 players cannot be initialized."""
        u4 = User.objects.create_user(username="p4", email="p4@example.com", password="pwd")
        GamePlayer.objects.create(game=self.game, user=u4, player_order=4, color="")
        self.assertEqual(self.game.players.count(), 4)
        with self.assertRaises(InvalidPlayersError):
            initialize_game(self.game)

    def test_reject_negative_player_score(self):
        """Tests that players with negative scores cause rejection."""
        # Update score directly via queryset to bypass clean()
        GamePlayer.objects.filter(id=self.p1.id).update(score=-10)
        with self.assertRaises(InvalidPlayersError):
            initialize_game(self.game)

    def test_reject_invalid_player_color(self):
        """Tests that players with unsupported colors are rejected."""
        GamePlayer.objects.filter(id=self.p1.id).update(color="purple")
        with self.assertRaises(InvalidPlayersError):
            initialize_game(self.game)

    def test_reject_missing_player_color(self):
        """Tests that players with empty color strings are rejected."""
        GamePlayer.objects.filter(id=self.p1.id).update(color="")
        with self.assertRaises(InvalidPlayersError):
            initialize_game(self.game)

    def test_reject_duplicate_player_colors(self):
        """Tests that duplicate player colors cause rejection at DB constraint and service levels."""
        with self.assertRaises(IntegrityError):
            GamePlayer.objects.create(game=self.game, user=self.host, player_order=4, color="red")

    def test_reject_if_player_already_has_capital(self):
        """Tests rejection if any player already has a capital record."""
        # Create a territory and capital for p1 in another context
        territory = Territory.objects.create(game=self.game, name="Тест", slug="test", owner=self.p1)
        Capital.objects.create(territory=territory, player=self.p1, health=3)
        with self.assertRaises(ExistingGameStateError):
            initialize_game(self.game)

    def test_reject_game_already_has_territories(self):
        """Tests that partially prepared or existing territories prevent initialization."""
        Territory.objects.create(game=self.game, name="София", slug="sofia")
        with self.assertRaises(ExistingGameStateError):
            initialize_game(self.game)

    def test_existing_rounds_are_preserved(self):
        """Tests that existing rounds are neither altered nor cause rejection."""
        cat = Category.objects.create(name="История")
        q = NumericQuestion.objects.create(category=cat, text="Коя година?", correct_answer=681)
        round_obj = Round.objects.create(
            game=self.game,
            number=1,
            question_type=Round.NUMERIC,
            numeric_question=q,
        )

        game = initialize_game(self.game)
        self.assertEqual(game.status, Game.ACTIVE)

        # Round still exists and is untouched
        round_refresh = Round.objects.get(id=round_obj.id)
        self.assertEqual(round_refresh.number, 1)
        self.assertEqual(round_refresh.status, Round.PENDING)
        self.assertEqual(round_refresh.numeric_question, q)

    def test_atomicity_and_rollback_on_failure(self):
        """Tests that an error midway rolls back all changes completely."""
        with patch.object(Game, "save", side_effect=RuntimeError("Database failure during save")):
            with self.assertRaises(RuntimeError):
                initialize_game(self.game)

        # Assert clean rollback
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, Game.WAITING)
        self.assertIsNone(self.game.started_at)
        self.assertEqual(self.game.territories.count(), 0)
        self.assertEqual(Capital.objects.filter(territory__game=self.game).count(), 0)

        # Retry after resolving error succeeds!
        game = initialize_game(self.game)
        self.assertEqual(game.status, Game.ACTIVE)
        self.assertEqual(game.territories.count(), 15)
        self.assertEqual(Capital.objects.filter(territory__game=game).count(), 3)

    def test_concurrency_double_initialization_rejected(self):
        """Tests that second attempt on same game is rejected without duplicate records."""
        initialize_game(self.game)
        with self.assertRaises(InvalidGameStatusError):
            initialize_game(self.game)

        self.assertEqual(self.game.territories.count(), 15)
        self.assertEqual(Capital.objects.filter(territory__game=self.game).count(), 3)

    def test_cannot_add_player_to_active_game(self):
        """Tests that adding a player to an active game is prohibited."""
        initialize_game(self.game)
        u4 = User.objects.create_user(username="p4", email="p4@example.com", password="pwd")
        new_player = GamePlayer(game=self.game, user=u4, player_order=4, color="blue")
        with self.assertRaises(ValidationError):
            new_player.clean()
        with self.assertRaises(ValidationError):
            new_player.save()

    def test_cannot_delete_player_from_active_game(self):
        """Tests that removing a player from an active game is prohibited."""
        initialize_game(self.game)
        with self.assertRaises(ValidationError):
            self.p1.delete()

    def test_cannot_change_player_composition_on_active_game(self):
        """Tests that modifying user or order of player on an active game is prohibited."""
        initialize_game(self.game)
        u4 = User.objects.create_user(username="p4", email="p4@example.com", password="pwd")
        self.p1.user = u4
        with self.assertRaises(ValidationError):
            self.p1.clean()
        with self.assertRaises(ValidationError):
            self.p1.save()

    def test_admin_permissions_on_active_game(self):
        """Tests that Admin denies player additions and deletions on active games."""
        initialize_game(self.game)

        site = AdminSite()
        player_admin = GamePlayerAdmin(GamePlayer, site)
        self.assertFalse(player_admin.has_delete_permission(None, self.p1))
        self.assertIn("user", player_admin.get_readonly_fields(None, self.p1))
        self.assertIn("player_order", player_admin.get_readonly_fields(None, self.p1))

        player_inline = GamePlayerInline(Game, site)
        self.assertFalse(player_inline.has_add_permission(None, self.game))
        self.assertFalse(player_inline.has_delete_permission(None, self.game))

    def test_find_all_independent_triplets_correctness(self):
        """Verifies that all triplets from find_all_independent_triplets are truly independent."""
        triplets = find_all_independent_triplets(BULGARIA_MAP_ADJACENCY)
        self.assertGreater(len(triplets), 0)
        for a, b, c in triplets:
            adj_a = set(BULGARIA_MAP_ADJACENCY[a])
            adj_b = set(BULGARIA_MAP_ADJACENCY[b])
            self.assertNotIn(b, adj_a)
            self.assertNotIn(c, adj_a)
            self.assertNotIn(c, adj_b)
