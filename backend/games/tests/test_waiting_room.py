from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from games.models import Game, WaitingPlayer
from games.waiting_room import form_game, join_w_room

User = get_user_model()

class WaitingRoomTests(TestCase):
    def setUp(self):
        userNames = ["pesho_pivovara", "gamer_boy99", "kotka12", "ivan_killer", "ninja_turtle"]
        self.users = [User.objects.create_user(n, f"{n}@gmail.com", f"p_{n}!") for n in userNames]

    def test_5_w_players(self):
        for u in self.users: join_w_room(u)
        self.assertEqual(WaitingPlayer.objects.count(), 5)
        newGame = form_game()
        self.assertEqual(newGame.status, Game.WAITING)
        self.assertEqual(newGame.players.count(), 3)
        self.assertEqual(WaitingPlayer.objects.count(), 2)
        for p in newGame.players.all():
            self.assertEqual(p.score, 0)
            self.assertIn(p.color, ["red", "green", "blue"])

    def test_2_w_player(self):
        for u in self.users[:2]: join_w_room(u)
        self.assertIsNone(form_game())
        self.assertEqual(Game.objects.count(), 0)
        self.assertEqual(WaitingPlayer.objects.count(), 2)

    def test_api_join_leave(self):
        apiClient = APIClient()
        apiClient.force_authenticate(user=self.users[0])
        res = apiClient.post(reverse("waiting-room-join"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(WaitingPlayer.objects.count(), 1)
        resDup = apiClient.post(reverse("waiting-room-join"))
        self.assertEqual(resDup.status_code, 400)
        resLeave = apiClient.post(reverse("waiting-room-leave"))
        self.assertEqual(resLeave.status_code, 200)
        self.assertEqual(WaitingPlayer.objects.count(), 0)
