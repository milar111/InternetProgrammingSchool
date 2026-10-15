from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from games.map import (
    BULGARIA_MAP_ADJACENCY,
    BULGARIA_MAP_TERRITORIES,
    SAMPLE_CAPITAL_TRIPLET,
    validate_game_map,
    validate_map_definition,
)
from games.models import Game, Territory

User = get_user_model()


class ProjectMapDefinitionTests(TestCase):
    def test_default_map_definition_is_valid(self):
        self.assertTrue(validate_map_definition())

    def test_territory_count_requirements(self):
        count = len(BULGARIA_MAP_TERRITORIES)
        self.assertEqual(count, 15)
        self.assertTrue(9 <= count <= 21)
        self.assertEqual(count % 3, 0)

    def test_all_nodes_have_at_least_two_neighbors(self):
        for slug, neighbors in BULGARIA_MAP_ADJACENCY.items():
            self.assertGreaterEqual(len(neighbors), 2, f"{slug} has fewer than 2 neighbors")

    def test_sample_capital_triplet_is_independent(self):
        a, b, c = SAMPLE_CAPITAL_TRIPLET
        self.assertNotIn(b, BULGARIA_MAP_ADJACENCY[a])
        self.assertNotIn(c, BULGARIA_MAP_ADJACENCY[a])
        self.assertNotIn(c, BULGARIA_MAP_ADJACENCY[b])

    def test_invalid_territory_count(self):
        small_territories = [{"name": f"T{i}", "slug": f"t{i}"} for i in range(8)]
        small_adj = {f"t{i}": [f"t{(i+1)%8}", f"t{(i-1)%8}"] for i in range(8)}
        with self.assertRaises(ValidationError):
            validate_map_definition(small_territories, small_adj)

    def test_duplicate_territory_name_or_slug(self):
        dup_names = [
            {"name": "София", "slug": "sofia-1"},
            {"name": "София", "slug": "sofia-2"},
        ] + [{"name": f"T{i}", "slug": f"t{i}"} for i in range(7)]
        adj = {t["slug"]: [] for t in dup_names}
        with self.assertRaises(ValidationError):
            validate_map_definition(dup_names, adj)

    def test_asymmetric_adjacency_raises_error(self):
        territories = [{"name": f"T{i}", "slug": f"t{i}"} for i in range(9)]
        adj = {f"t{i}": [f"t{(i+1)%9}", f"t{(i-1)%9}"] for i in range(9)}
        # Break symmetry
        adj["t0"].append("t2")
        with self.assertRaises(ValidationError):
            validate_map_definition(territories, adj)

    def test_disconnected_graph_raises_error(self):
        territories = [{"name": f"T{i}", "slug": f"t{i}"} for i in range(9)]
        # two disconnected triangles + one triangle
        adj = {
            "t0": ["t1", "t2"], "t1": ["t0", "t2"], "t2": ["t0", "t1"],
            "t3": ["t4", "t5"], "t4": ["t3", "t5"], "t5": ["t3", "t4"],
            "t6": ["t7", "t8"], "t7": ["t6", "t8"], "t8": ["t6", "t7"],
        }
        with self.assertRaises(ValidationError):
            validate_map_definition(territories, adj)


class GameMapValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="host", email="host@example.com", password="pwd")
        self.game = Game.objects.create(created_by=self.user)
        self.other_game = Game.objects.create(created_by=self.user)

    def test_empty_game_map_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            validate_game_map(self.game)

    def test_partial_game_map_raises_validation_error(self):
        Territory.objects.create(game=self.game, name="София", slug="sofia")
        Territory.objects.create(game=self.game, name="Варна", slug="varna")
        with self.assertRaises(ValidationError):
            validate_game_map(self.game)

    def test_full_valid_game_map_passes_validation(self):
        by_slug = {}
        for item in BULGARIA_MAP_TERRITORIES:
            by_slug[item["slug"]] = Territory.objects.create(
                game=self.game,
                name=item["name"],
                slug=item["slug"],
            )

        for slug, neighbors in BULGARIA_MAP_ADJACENCY.items():
            territory = by_slug[slug]
            for neighbor_slug in neighbors:
                territory.neighbors.add(by_slug[neighbor_slug])

        self.assertTrue(validate_game_map(self.game))

    def test_cross_game_neighbors_rejected(self):
        by_slug = {}
        for item in BULGARIA_MAP_TERRITORIES:
            by_slug[item["slug"]] = Territory.objects.create(
                game=self.game,
                name=item["name"],
                slug=item["slug"],
            )

        for slug, neighbors in BULGARIA_MAP_ADJACENCY.items():
            territory = by_slug[slug]
            for neighbor_slug in neighbors:
                territory.neighbors.add(by_slug[neighbor_slug])

        other_territory = Territory.objects.create(game=self.other_game, name="София", slug="sofia")
        by_slug["sofia"].neighbors.add(other_territory)

        with self.assertRaises(ValidationError):
            validate_game_map(self.game)

    def test_missing_neighbors_rejected(self):
        by_slug = {}
        for item in BULGARIA_MAP_TERRITORIES:
            by_slug[item["slug"]] = Territory.objects.create(
                game=self.game,
                name=item["name"],
                slug=item["slug"],
            )
        # Territories created without neighbors
        with self.assertRaises(ValidationError):
            validate_game_map(self.game)
