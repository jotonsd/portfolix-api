import logging

from django.db import transaction
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Plan, UserSubscription, User, Transaction
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
    if user.user_type in (User.ADMIN, User.STAFF):
        return
    plan = Plan.objects.get(name=Plan.FREE)
    UserSubscription.objects.get_or_create(user=user, defaults={'plan': plan})


def _handle_social_login(info: dict, id_field: str):
    with transaction.atomic():
        user, created = User.objects.get_or_create(
            email=info['email'],
            defaults={
                'first_name': info['first_name'],
                'last_name': info['last_name'],
                id_field: info[id_field],
                'is_active': True,
            },
        )
        if not created and info[id_field] and not getattr(user, id_field):
            setattr(user, id_field, info[id_field])
            user.save(update_fields=[id_field])
        if created:
            user.set_unusable_password()
            user.save()
            _assign_free_plan(user)
    return user, created


class RegisterView(APIView):
    authentication_classes = []
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
    authentication_classes = []
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
    authentication_classes = []
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
        user, created = _handle_social_login(info, 'google_id')
        logger.info("Google login: %s (new=%s)", user.email, created)
        return Response({'user': ProfileSerializer(user).data, 'tokens': _tokens(user)})


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
        user, created = _handle_social_login(info, 'facebook_id')
        logger.info("Facebook login: %s (new=%s)", user.email, created)
        return Response({'user': ProfileSerializer(user).data, 'tokens': _tokens(user)})


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
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        plans = Plan.objects.all()
        return Response(PlanSerializer(plans, many=True).data)


class TokenRefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser]

    def post(self, request):
        token = request.data.get('refresh')
        if not token:
            return Response({'error': 'Refresh token required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh = RefreshToken(token)
            return Response({'access': str(refresh.access_token)})
        except TokenError:
            return Response({'error': 'Invalid or expired refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)


import stripe
from django.conf import settings as django_settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

stripe.api_key = django_settings.STRIPE_SECRET_KEY

PLAN_CONFIG = {
    'starter': {'name': 'Portfolix Starter', 'amount': 1900, 'currency': 'usd'},
    'pro':     {'name': 'Portfolix Pro',     'amount': 4900, 'currency': 'usd'},
}


class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_name = request.data.get('plan')
        config = PLAN_CONFIG.get(plan_name)
        if not config:
            return Response({'error': 'Invalid plan.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price_data': {
                        'currency': config['currency'],
                        'unit_amount': config['amount'],
                        'recurring': {'interval': 'month'},
                        'product_data': {'name': config['name']},
                    },
                    'quantity': 1,
                }],
                success_url=f"{django_settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{django_settings.FRONTEND_URL}/payment/cancel",
                customer_email=request.user.email,
                metadata={'user_id': str(request.user.id), 'plan': plan_name},
            )
            return Response({'url': session.url})
        except Exception as e:
            logger.error("Stripe checkout error: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        import json
        payload = request.body
        webhook_secret = django_settings.STRIPE_WEBHOOK_SECRET
        if webhook_secret:
            sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
            try:
                stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            except (ValueError, stripe.error.SignatureVerificationError):
                return Response({'error': 'Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            event = json.loads(payload)
        except Exception:
            return Response({'error': 'Invalid payload.'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info("Webhook event type: %s", event['type'])

        if event['type'] == 'checkout.session.completed':
            try:
                session = event['data']['object']
                metadata = session.get('metadata') or {}
                user_id = metadata.get('user_id')
                plan_name = metadata.get('plan')
                stripe_sub_id = session.get('subscription') or ''
                logger.info("Checkout complete: user_id=%s plan=%s sub=%s", user_id, plan_name, stripe_sub_id)

                if user_id and plan_name:
                    user = User.objects.get(id=int(user_id))
                    plan = Plan.objects.get(name=plan_name)
                    sub, _ = UserSubscription.objects.get_or_create(user=user, defaults={'plan': plan})
                    sub.plan = plan
                    sub.period_start = timezone.now()
                    sub.stripe_subscription_id = stripe_sub_id
                    sub.save(update_fields=['plan', 'period_start', 'stripe_subscription_id'])
                    amount_total = session.get('amount_total') or 0
                    currency = session.get('currency', 'usd')
                    session_id = session.get('id') or None
                    Transaction.objects.get_or_create(
                        stripe_session_id=session_id,
                        defaults=dict(
                            user=user,
                            amount=amount_total,
                            currency=currency,
                            plan=plan_name,
                            type=Transaction.PAYMENT,
                            status=Transaction.STATUS_PAID,
                            description=f"Portfolix {plan.display_name} subscription",
                            stripe_subscription_id=stripe_sub_id,
                        ),
                    )
                    logger.info("Upgraded user %s to %s", user.email, plan_name)
                else:
                    logger.warning("Missing user_id or plan in metadata: %s", metadata)
            except Exception as e:
                logger.error("Webhook upgrade error: %s", e, exc_info=True)
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'status': 'ok'})
