from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import Profile

User = get_user_model()


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/auth/register/"
        self.login_url = "/api/auth/login/"
        self.logout_url = "/api/auth/logout/"
        self.me_url = "/api/auth/me/"
        self.csrf_url = "/api/auth/csrf/"

    def test_successful_registration(self):
        payload = {
            "username": "player_one",
            "email": "player@example.com",
            "nickname": "MountainKnight",
            "password": "example-password",
            "password_confirm": "example-password",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="player_one")
        self.assertEqual(user.email, "player@example.com")
        self.assertTrue(user.check_password("example-password"))
        self.assertEqual(user.profile.nickname, "MountainKnight")
        self.assertEqual(user.profile.avatar_key, "knight-1")

        self.assertEqual(response.data["username"], "player_one")
        self.assertEqual(response.data["profile"]["nickname"], "MountainKnight")
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_confirm", response.data)

    def test_invalid_registration_scenarios(self):
        initial_user = User.objects.create_user(
            username="existing_user",
            email="existing@example.com",
            password="pwd",
        )
        Profile.objects.create(user=initial_user, nickname="ExistingKnight")
        initial_count = User.objects.count()

        scenarios = [
            (
                {
                    "username": "existing_user",
                    "email": "unique1@example.com",
                    "nickname": "UniqueKnight1",
                    "password": "pwd",
                    "password_confirm": "pwd",
                },
                "username",
            ),
            (
                {
                    "username": "unique_user1",
                    "email": "existing@example.com",
                    "nickname": "UniqueKnight2",
                    "password": "pwd",
                    "password_confirm": "pwd",
                },
                "email",
            ),
            (
                {
                    "username": "unique_user2",
                    "email": "unique2@example.com",
                    "nickname": "ExistingKnight",
                    "password": "pwd",
                    "password_confirm": "pwd",
                },
                "nickname",
            ),
            (
                {
                    "username": "unique_user3",
                    "email": "unique3@example.com",
                    "nickname": "UniqueKnight3",
                    "password": "pwd1",
                    "password_confirm": "pwd2",
                },
                "password_confirm",
            ),
        ]

        for payload, error_key in scenarios:
            with self.subTest(error_key=error_key):
                response = self.client.post(self.register_url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("errors", response.data)
                self.assertIn(error_key, response.data["errors"])

        self.assertEqual(User.objects.count(), initial_count)

    def test_successful_login_and_session(self):
        user = User.objects.create_user(
            username="login_user",
            email="login@example.com",
            password="secretpassword",
        )
        Profile.objects.create(user=user, nickname="LoginKnight")

        response = self.client.post(
            self.login_url,
            {"username": "login_user", "password": "secretpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "login_user")
        self.assertIn("sessionid", response.cookies)

        me_response = self.client.get(self.me_url)
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["username"], "login_user")
        self.assertEqual(me_response.data["profile"]["nickname"], "LoginKnight")

    def test_failed_login(self):
        User.objects.create_user(
            username="user_fail",
            email="fail@example.com",
            password="correct-pwd",
        )

        response = self.client.post(
            self.login_url,
            {"username": "user_fail", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "Invalid credentials.")
        self.assertIn("errors", response.data)

        me_response = self.client.get(self.me_url)
        self.assertIn(
            me_response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_me_permissions(self):
        anon_response = self.client.get(self.me_url)
        self.assertIn(
            anon_response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

        user = User.objects.create_user(
            username="perm_user",
            email="perm@example.com",
            password="pwd",
        )
        Profile.objects.create(user=user, nickname="PermKnight")

        self.client.force_login(user)
        auth_response = self.client.get(self.me_url)
        self.assertEqual(auth_response.status_code, status.HTTP_200_OK)
        self.assertEqual(auth_response.data["username"], "perm_user")

    def test_profile_update(self):
        user = User.objects.create_user(
            username="edit_user",
            email="edit@example.com",
            password="pwd",
        )
        Profile.objects.create(user=user, nickname="OldNick", avatar_key="knight-1")
        self.client.force_login(user)

        update_payload = {"nickname": "NewNick", "avatar_key": "knight-3"}
        response = self.client.patch(self.me_url, update_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["nickname"], "NewNick")
        self.assertEqual(response.data["profile"]["avatar_key"], "knight-3")

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.nickname, "NewNick")
        self.assertEqual(user.profile.avatar_key, "knight-3")

        forbidden_response = self.client.patch(
            self.me_url, {"is_staff": True}, format="json"
        )
        self.assertEqual(forbidden_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", forbidden_response.data)
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    def test_logout(self):
        user = User.objects.create_user(
            username="logout_user",
            email="logout@example.com",
            password="pwd",
        )
        Profile.objects.create(user=user, nickname="LogoutKnight")

        self.client.post(
            self.login_url,
            {"username": "logout_user", "password": "pwd"},
            format="json",
        )
        logout_response = self.client.post(self.logout_url)
        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

        me_response = self.client.get(self.me_url)
        self.assertIn(
            me_response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_csrf_protection(self):
        csrf_client = APIClient(enforce_csrf_checks=True)

        user = User.objects.create_user(
            username="csrf_user",
            email="csrf@example.com",
            password="pwd",
        )
        Profile.objects.create(user=user, nickname="CsrfKnight")

        csrf_res = csrf_client.get(self.csrf_url)
        self.assertEqual(csrf_res.status_code, status.HTTP_204_NO_CONTENT)
        csrf_token = csrf_res.cookies["csrftoken"].value

        csrf_client.force_login(user)

        denied_res = csrf_client.patch(
            self.me_url,
            {"nickname": "NoTokenKnight"},
            format="json",
        )
        self.assertEqual(denied_res.status_code, status.HTTP_403_FORBIDDEN)

        allowed_res = csrf_client.patch(
            self.me_url,
            {"nickname": "WithTokenKnight"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(allowed_res.status_code, status.HTTP_200_OK)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.nickname, "WithTokenKnight")

    def test_get_current_profile(self):
        user = get_user_model().objects.create_user(
            username="player_one",
            email="player@example.com",
            password="example-password",
        )
        self.client.login(username="player_one", password="example-password")
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nickname", response.data)
        self.assertEqual(response.data["nickname"], "player_one")
        self.assertIn("avatar_key", response.data)
