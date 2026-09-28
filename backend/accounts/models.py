from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    nickname = models.CharField(max_length=30, unique=True)
    avatar_key = models.CharField(max_length=30, default="knight-1")

    def __str__(self):
        return f"{self.nickname} ({self.user.username})"
