import logging

from django.db import transaction
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Plan, UserSubscription, User
from .serializers import (
    RegisterSerializer, LoginSerializer, SocialAuthSerializer,
    ProfileSerializer, PlanSerializer,
)
from .services.google_auth import verify_google_token
from .services.facebook_auth import verify_facebook_token

logger = logging.getLogger('accounts')


def _tokens(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def _assign_free_plan(user):
    plan = Plan.objects.get(name=Plan.FREE)
    UserSubscription.objects.get_or_create(user=user, defaults={'plan': plan})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = serializer.save()
            _assign_free_plan(user)

        logger.info("New user registered: %s", user.email)
        return Response({
            'user': ProfileSerializer(user).data,
            'tokens': _tokens(user),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        logger.info("User logged in: %s", user.email)
        return Response({
            'user': ProfileSerializer(user).data,
            'tokens': _tokens(user),
        })


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser]

    def post(self, request):
        serializer = SocialAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            info = verify_google_token(serializer.validated_data['access_token'])
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=info['email'],
                defaults={
                    'first_name': info['first_name'],
                    'last_name': info['last_name'],
                    'google_id': info['google_id'],
                    'is_active': True,
                },
            )
            if not created and info['google_id'] and not user.google_id:
                user.google_id = info['google_id']
                user.save(update_fields=['google_id'])
            if created:
                user.set_unusable_password()
                user.save()
                _assign_free_plan(user)

        logger.info("Google login: %s (new=%s)", user.email, created)
        return Response({
            'user': ProfileSerializer(user).data,
            'tokens': _tokens(user),
        })


class FacebookLoginView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser]

    def post(self, request):
        serializer = SocialAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            info = verify_facebook_token(serializer.validated_data['access_token'])
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=info['email'],
                defaults={
                    'first_name': info['first_name'],
                    'last_name': info['last_name'],
                    'facebook_id': info['facebook_id'],
                    'is_active': True,
                },
            )
            if not created and info['facebook_id'] and not user.facebook_id:
                user.facebook_id = info['facebook_id']
                user.save(update_fields=['facebook_id'])
            if created:
                user.set_unusable_password()
                user.save()
                _assign_free_plan(user)

        logger.info("Facebook login: %s (new=%s)", user.email, created)
        return Response({
            'user': ProfileSerializer(user).data,
            'tokens': _tokens(user),
        })


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class PlanListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        plans = Plan.objects.all()
        return Response(PlanSerializer(plans, many=True).data)


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser]

    def post(self, request):
        token = request.data.get('refresh')
        if not token:
            return Response({'error': 'Refresh token required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh = RefreshToken(token)
            return Response({'access': str(refresh.access_token)})
        except Exception:
            return Response({'error': 'Invalid or expired refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)
