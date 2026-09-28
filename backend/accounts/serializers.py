from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from .models import Profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    FORBIDDEN_FIELDS = [
        "id", "username", "email", "password", "is_staff",
        "is_superuser", "groups", "user_permissions",
    ]

    class Meta:
        model = Profile
        fields = ["nickname", "avatar_key"]

    def validate(self, attrs):
        for field in self.FORBIDDEN_FIELDS:
            if field in self.initial_data:
                raise serializers.ValidationError({field: [f"Cannot change {field}."]})
        return attrs


ProfileUpdateSerializer = ProfileSerializer



class UserSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(source="profile.nickname", read_only=True)
    avatar_key = serializers.CharField(source="profile.avatar_key", read_only=True)
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "nickname", "avatar_key", "profile"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    nickname = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("User with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def validate_nickname(self, value):
        if Profile.objects.filter(nickname=value).exists():
            raise serializers.ValidationError("User with this nickname already exists.")
        return value

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": ["Passwords do not match."]})
        return data

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
            )
            Profile.objects.create(
                user=user,
                nickname=validated_data["nickname"],
                avatar_key="knight-1",
            )
        return user
