from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from accounts.models import Profile

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_with_unique_email_and_password_hashing(self):
        user = User.objects.create_user(
            username="player1",
            email="player1@example.com",
            password="secure-password-123",
        )
        self.assertEqual(user.username, "player1")
        self.assertEqual(user.email, "player1@example.com")
        self.assertTrue(user.check_password("secure-password-123"))
        self.assertFalse(user.check_password("wrong-password"))
        self.assertNotEqual(user.password, "secure-password-123")

    def test_duplicate_email_raises_integrity_error(self):
        User.objects.create_user(
            username="player1",
            email="duplicate@example.com",
            password="password123",
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="player2",
                email="duplicate@example.com",
                password="password123",
            )

    def test_duplicate_username_raises_integrity_error(self):
        User.objects.create_user(
            username="same_user",
            email="user1@example.com",
            password="password123",
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="same_user",
                email="user2@example.com",
                password="password123",
            )


class ProfileModelTests(TestCase):
    def test_profile_creation_and_defaults(self):
        user = User.objects.create_user(
            username="knight_user",
            email="knight@example.com",
            password="password123",
        )
        profile = Profile.objects.create(
            user=user,
            nickname="ValiantKnight",
        )
        self.assertEqual(profile.user, user)
        self.assertEqual(profile.nickname, "ValiantKnight")
        self.assertEqual(profile.avatar_key, "knight-1")
        self.assertEqual(user.profile, profile)

    def test_duplicate_nickname_raises_integrity_error(self):
        user1 = User.objects.create_user(
            username="u1", email="u1@example.com", password="pwd"
        )
        user2 = User.objects.create_user(
            username="u2", email="u2@example.com", password="pwd"
        )
        Profile.objects.create(user=user1, nickname="UniqueKnight")
        with self.assertRaises(IntegrityError):
            Profile.objects.create(user=user2, nickname="UniqueKnight")
