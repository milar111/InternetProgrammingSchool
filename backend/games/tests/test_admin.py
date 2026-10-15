from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from games.admin import CapitalAdmin, TerritoryAdmin
from games.models import Capital, Game, GamePlayer, Territory

User = get_user_model()


class GamesAdminConfigurationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/")
        self.user = User.objects.create_user(username="admin", email="admin@example.com", is_staff=True)
        self.request.user = self.user

    def test_territory_and_capital_are_registered(self):
        self.assertIn(Territory, site._registry)
        self.assertIsInstance(site._registry[Territory], TerritoryAdmin)

        self.assertIn(Capital, site._registry)
        self.assertIsInstance(site._registry[Capital], CapitalAdmin)

    def test_territory_admin_permissions_and_options(self):
        admin_obj = site._registry[Territory]

        self.assertFalse(admin_obj.has_add_permission(self.request))
        self.assertFalse(admin_obj.has_delete_permission(self.request))
        self.assertIsNone(admin_obj.actions)

        for field in ("game", "name", "slug", "owner", "neighbors"):
            self.assertIn(field, admin_obj.readonly_fields)

        self.assertIn("score", admin_obj.list_display)

    def test_capital_admin_permissions_and_options(self):
        admin_obj = site._registry[Capital]

        self.assertFalse(admin_obj.has_add_permission(self.request))
        self.assertFalse(admin_obj.has_delete_permission(self.request))
        self.assertIsNone(admin_obj.actions)

        for field in ("player", "territory"):
            self.assertIn(field, admin_obj.readonly_fields)

        self.assertIn("health", admin_obj.list_display)

    def test_territory_admin_get_neighbors_display(self):
        admin_obj = site._registry[Territory]
        game = Game.objects.create(created_by=self.user)
        t1 = Territory.objects.create(game=game, name="София", slug="sofia")
        t2 = Territory.objects.create(game=game, name="Враца", slug="vratsa")
        t1.neighbors.add(t2)

        display = admin_obj.get_neighbors(t1)
        self.assertEqual(display, "Враца")

    def test_capital_admin_get_game_display(self):
        admin_obj = site._registry[Capital]
        game = Game.objects.create(created_by=self.user)
        player = GamePlayer.objects.create(game=game, user=self.user, player_order=1)
        territory = Territory.objects.create(game=game, name="София", slug="sofia", owner=player)
        capital = Capital.objects.create(territory=territory, player=player)

        self.assertEqual(admin_obj.get_game(capital), game)

    def test_admin_works_with_no_games(self):
        Territory.objects.all().delete()
        Capital.objects.all().delete()
        Game.objects.all().delete()

        admin_territory = site._registry[Territory]
        admin_capital = site._registry[Capital]

        qs_t = admin_territory.get_queryset(self.request)
        qs_c = admin_capital.get_queryset(self.request)

        self.assertEqual(qs_t.count(), 0)
        self.assertEqual(qs_c.count(), 0)
