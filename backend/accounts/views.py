from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Profile
from .serializers import RegisterSerializer, UserSerializer, ProfileSerializer


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        get_token(request)
        return Response(status=204)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=201)
        return Response({"errors": serializer.errors}, status=400)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(request, username=username, password=password)
        if not user:
            return Response(
                {
                    "error": "Invalid credentials.",
                    "errors": {"non_field_errors": ["Invalid credentials."]},
                },
                status=400,
            )

        login(request, user)
        return Response(UserSerializer(user).data, status=200)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=204)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        Profile.objects.get_or_create(
            user=request.user,
            defaults={"nickname": request.user.username[:30], "avatar_key": "knight-1"},
        )
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(
            user=request.user,
            defaults={"nickname": request.user.username[:30], "avatar_key": "knight-1"},
        )
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(request.user).data)
        return Response({"errors": serializer.errors}, status=400)
