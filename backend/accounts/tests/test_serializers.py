from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from accounts.models import Profile
from accounts.serializers import (
    ProfileSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterSerializerTests(TestCase):
    def test_valid_registration_creates_user_and_profile(self):
        data = {
            "username": "player_one",
            "email": "player@example.com",
            "nickname": "MountainKnight",
            "password": "example-password",
            "password_confirm": "example-password",
        }
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertEqual(user.username, "player_one")
        self.assertEqual(user.email, "player@example.com")
        self.assertTrue(user.check_password("example-password"))
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(user.profile.nickname, "MountainKnight")
        self.assertEqual(user.profile.avatar_key, "knight-1")

    def test_password_mismatch_fails_validation(self):
        data = {
            "username": "player_mismatch",
            "email": "mismatch@example.com",
            "nickname": "MismatchKnight",
            "password": "password123",
            "password_confirm": "different123",
        }
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password_confirm", serializer.errors)

    def test_duplicate_username_fails_validation(self):
        User.objects.create_user(username="taken", email="u@example.com", password="pwd")
        data = {
            "username": "taken",
            "email": "new@example.com",
            "nickname": "NewKnight",
            "password": "password123",
            "password_confirm": "password123",
        }
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)

    def test_duplicate_email_fails_validation(self):
        User.objects.create_user(username="u1", email="taken@example.com", password="pwd")
        data = {
            "username": "new_user",
            "email": "taken@example.com",
            "nickname": "NewKnight2",
            "password": "password123",
            "password_confirm": "password123",
        }
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_duplicate_nickname_fails_validation(self):
        u = User.objects.create_user(username="u1", email="u1@example.com", password="pwd")
        Profile.objects.create(user=u, nickname="TakenKnight")
        data = {
            "username": "new_user2",
            "email": "new2@example.com",
            "nickname": "TakenKnight",
            "password": "password123",
            "password_confirm": "password123",
        }
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("nickname", serializer.errors)


class ProfileUpdateSerializerTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            nickname="OldKnight",
            avatar_key="knight-1",
        )
        self.request = self.factory.get("/")
        self.request.user = self.user

    def test_valid_profile_update(self):
        serializer = ProfileUpdateSerializer(
            self.profile,
            data={"nickname": "UpdatedKnight", "avatar_key": "knight-3"},
            partial=True,
            context={"request": self.request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_profile = serializer.save()
        self.assertEqual(updated_profile.nickname, "UpdatedKnight")
        self.assertEqual(updated_profile.avatar_key, "knight-3")

    def test_forbidden_field_rejected(self):
        serializer = ProfileUpdateSerializer(
            self.profile,
            data={"nickname": "UpdatedKnight", "is_staff": True},
            partial=True,
            context={"request": self.request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("is_staff", serializer.errors)
