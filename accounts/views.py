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
                    # Get exact billing period end from Stripe subscription item
                    expires_at = None
                    if stripe_sub_id:
                        try:
                            from datetime import datetime, timezone as dt_tz
                            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id, expand=['items'])
                            items = stripe_sub.get('items', {}).get('data', [])
                            period_end = items[0].get('current_period_end') if items else None
                            if period_end:
                                expires_at = datetime.fromtimestamp(period_end, tz=dt_tz.utc)
                        except Exception:
                            pass
                    sub.expires_at = expires_at
                    sub.save(update_fields=['plan', 'period_start', 'stripe_subscription_id', 'expires_at'])
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

        elif event['type'] == 'invoice.payment_succeeded':
            # Renewal payment succeeded — record the transaction
            try:
                invoice = event['data']['object']
                stripe_sub_id = invoice.get('subscription') or ''
                if not stripe_sub_id:
                    return Response({'status': 'ok'})
                # Skip the initial invoice (already recorded via checkout.session.completed)
                if invoice.get('billing_reason') == 'subscription_create':
                    return Response({'status': 'ok'})
                sub = UserSubscription.objects.select_related('user', 'plan').get(
                    stripe_subscription_id=stripe_sub_id
                )
                amount = invoice.get('amount_paid') or 0
                currency = invoice.get('currency', 'usd')
                invoice_id = invoice.get('id') or ''
                Transaction.objects.get_or_create(
                    stripe_invoice_id=invoice_id,
                    defaults=dict(
                        user=sub.user,
                        amount=amount,
                        currency=currency,
                        plan=sub.plan.name,
                        type=Transaction.PAYMENT,
                        status=Transaction.STATUS_PAID,
                        description=f"Portfolix {sub.plan.display_name} renewal",
                        stripe_subscription_id=stripe_sub_id,
                    ),
                )
                # Reset monthly counter and set next period end
                sub.cv_count = 0
                sub.period_start = timezone.now()
                period_end_ts = invoice.get('lines', {}).get('data', [{}])[0].get('period', {}).get('end')
                if period_end_ts:
                    from datetime import datetime, timezone as dt_tz
                    sub.expires_at = datetime.fromtimestamp(period_end_ts, tz=dt_tz.utc)
                sub.save(update_fields=['cv_count', 'period_start', 'expires_at'])
                logger.info("Renewal recorded for %s plan=%s", sub.user.email, sub.plan.name)
            except UserSubscription.DoesNotExist:
                logger.warning("No subscription found for stripe_sub_id=%s", stripe_sub_id)
            except Exception as e:
                logger.error("Renewal recording error: %s", e, exc_info=True)

        elif event['type'] == 'invoice.payment_failed':
            # Payment failed — log it; Stripe will retry automatically
            try:
                invoice = event['data']['object']
                stripe_sub_id = invoice.get('subscription') or ''
                attempt = invoice.get('attempt_count', 1)
                logger.warning("Payment failed (attempt %s) for subscription %s", attempt, stripe_sub_id)
                # Record a failed transaction so it shows in the ledger
                if stripe_sub_id:
                    try:
                        sub = UserSubscription.objects.select_related('user', 'plan').get(
                            stripe_subscription_id=stripe_sub_id
                        )
                        invoice_id = invoice.get('id') or ''
                        amount = invoice.get('amount_due') or 0
                        currency = invoice.get('currency', 'usd')
                        Transaction.objects.get_or_create(
                            stripe_invoice_id=invoice_id,
                            defaults=dict(
                                user=sub.user,
                                amount=amount,
                                currency=currency,
                                plan=sub.plan.name,
                                type=Transaction.PAYMENT,
                                status=Transaction.STATUS_FAILED,
                                description=f"Portfolix {sub.plan.display_name} renewal (failed — attempt {attempt})",
                                stripe_subscription_id=stripe_sub_id,
                            ),
                        )
                    except UserSubscription.DoesNotExist:
                        pass
            except Exception as e:
                logger.error("Payment failed handler error: %s", e, exc_info=True)

        elif event['type'] == 'customer.subscription.deleted':
            # Stripe gave up retrying — downgrade user to free plan
            try:
                subscription = event['data']['object']
                stripe_sub_id = subscription.get('id') or ''
                logger.info("Subscription cancelled: %s", stripe_sub_id)
                if stripe_sub_id:
                    try:
                        sub = UserSubscription.objects.select_related('user', 'plan').get(
                            stripe_subscription_id=stripe_sub_id
                        )
                        old_plan_name = sub.plan.name
                        free_plan = Plan.objects.get(name=Plan.FREE)
                        sub.plan = free_plan
                        sub.stripe_subscription_id = ''
                        sub.cv_count = 0
                        sub.period_start = timezone.now()
                        sub.save(update_fields=['plan', 'stripe_subscription_id', 'cv_count', 'period_start'])
                        logger.info(
                            "Downgraded %s from %s to free (subscription deleted)",
                            sub.user.email, old_plan_name,
                        )
                    except UserSubscription.DoesNotExist:
                        logger.warning("No subscription found for cancelled stripe_sub_id=%s", stripe_sub_id)
            except Exception as e:
                logger.error("Subscription deleted handler error: %s", e, exc_info=True)

        return Response({'status': 'ok'})
