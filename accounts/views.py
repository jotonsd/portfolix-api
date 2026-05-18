import logging

from django.db import transaction
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Plan, UserSubscription, User, Transaction, RefundRequest
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

    picture = info.get('picture', '')
    if picture and not user.avatar:
        user.avatar = picture
        user.save(update_fields=['avatar'])

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
        avatar_file = request.FILES.get('avatar')
        if avatar_file:
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            path = default_storage.save(f'avatars/{avatar_file.name}', ContentFile(avatar_file.read()))
            url = f'{django_settings.BASE_URL.rstrip("/")}{django_settings.MEDIA_URL}{path}'
            request.user.avatar = url
            request.user.save(update_fields=['avatar'])

        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class OnboardingView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser]

    def post(self, request):
        user = request.user
        user.profession = request.data.get('profession', '')
        user.job_hunting = request.data.get('job_hunting', '')
        user.onboarding_completed = True
        user.save(update_fields=['profession', 'job_hunting', 'onboarding_completed'])
        return Response(ProfileSerializer(user).data)


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
    'starter': {
        'monthly': {'name': 'Portfolix Starter',          'amount':  900, 'interval': 'month'},
        'yearly':  {'name': 'Portfolix Starter (Yearly)', 'amount': 6000, 'interval': 'year'},
    },
    'pro': {
        'monthly': {'name': 'Portfolix Pro',              'amount': 1900,  'interval': 'month'},
        'yearly':  {'name': 'Portfolix Pro (Yearly)',     'amount': 12000, 'interval': 'year'},
    },
}

REFUND_PROCESSING_FEE = 100  # $1.00 in cents


def _calc_refund(original_amount: int, cv_used: int, cv_limit: int) -> dict:
    """Return refund breakdown given original amount (cents), usage counts."""
    if cv_limit <= 0:
        usage_pct = 0
    else:
        usage_pct = min(100, round((cv_used / cv_limit) * 100))
    usage_deduction = round(original_amount * usage_pct / 100)
    refund_amount = max(0, original_amount - usage_deduction - REFUND_PROCESSING_FEE)
    return {
        'usage_pct': usage_pct,
        'usage_deduction': usage_deduction,
        'processing_fee': REFUND_PROCESSING_FEE,
        'refund_amount': refund_amount,
    }


class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_name = request.data.get('plan')
        billing   = request.data.get('billing', 'monthly')
        if billing not in ('monthly', 'yearly'):
            billing = 'monthly'

        plan_options = PLAN_CONFIG.get(plan_name)
        if not plan_options:
            return Response({'error': 'Invalid plan.'}, status=status.HTTP_400_BAD_REQUEST)
        config = plan_options[billing]

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': config['amount'],
                        'recurring': {'interval': config['interval']},
                        'product_data': {'name': config['name']},
                    },
                    'quantity': 1,
                }],
                success_url=f"{django_settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{django_settings.FRONTEND_URL}/payment/cancel",
                customer_email=request.user.email,
                metadata={'user_id': str(request.user.id), 'plan': plan_name, 'billing': billing},
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
                            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
                            # stripe-python ≥5: attribute access, no .get()
                            items_data = getattr(getattr(stripe_sub, 'items', None), 'data', [])
                            period_end = getattr(items_data[0], 'current_period_end', None) if items_data else None
                            if period_end:
                                expires_at = datetime.fromtimestamp(period_end, tz=dt_tz.utc)
                        except Exception:
                            pass
                    sub.expires_at = expires_at
                    sub.save(update_fields=['plan', 'period_start', 'stripe_subscription_id', 'expires_at'])
                    amount_total = session.get('amount_total') or 0
                    currency = session.get('currency', 'usd')
                    session_id = session.get('id') or None

                    # Try to capture payment_intent_id from the subscription_create invoice.
                    # Stripe API 2025-07-30.basil removed payment_intent from invoice responses;
                    # pin to 2024-04-10 for this lookup so the field is still present.
                    stripe_pi_id = ''
                    if stripe_sub_id:
                        try:
                            invoices = stripe.Invoice.list(
                                subscription=stripe_sub_id,
                                limit=5,
                                expand=['data.payment_intent'],
                                stripe_version='2024-04-10',
                            )
                            for inv in invoices.data:
                                if getattr(inv, 'billing_reason', None) == 'subscription_create':
                                    pi = getattr(inv, 'payment_intent', None)
                                    if pi:
                                        stripe_pi_id = pi if isinstance(pi, str) else pi.id
                                    break
                        except Exception:
                            pass  # Non-fatal; invoice.payment_succeeded webhook is the fallback

                    tx, created = Transaction.objects.get_or_create(
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
                            stripe_payment_intent_id=stripe_pi_id,
                        ),
                    )
                    if not created and stripe_pi_id and not tx.stripe_payment_intent_id:
                        tx.stripe_payment_intent_id = stripe_pi_id
                        tx.save(update_fields=['stripe_payment_intent_id'])
                    logger.info("Upgraded user %s to %s pi=%s", user.email, plan_name, stripe_pi_id or '(pending)')
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
                # The initial invoice is already recorded via checkout.session.completed,
                # but we use this event to capture the payment_intent_id for future refunds.
                # Note: Stripe API 2025-07-30.basil removed payment_intent from invoice payloads;
                # the webhook payload uses the endpoint's pinned API version, so this may be empty.
                if invoice.get('billing_reason') == 'subscription_create':
                    pi_id = invoice.get('payment_intent') or ''
                    if pi_id and stripe_sub_id:
                        Transaction.objects.filter(
                            stripe_subscription_id=stripe_sub_id,
                            stripe_payment_intent_id='',
                        ).update(stripe_payment_intent_id=pi_id)
                        logger.info("Stored payment_intent %s on transaction for sub %s", pi_id, stripe_sub_id)
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


class RefundEstimateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transaction_id = request.query_params.get('transaction_id')
        if not transaction_id:
            return Response({'error': 'transaction_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            original = Transaction.objects.get(
                id=transaction_id,
                user=request.user,
                type=Transaction.PAYMENT,
                status=Transaction.STATUS_PAID,
            )
        except Transaction.DoesNotExist:
            return Response({'error': 'Transaction not found or not eligible.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            sub = UserSubscription.objects.select_related('plan').get(user=request.user)
            cv_limit = sub.plan.cv_limit if sub.plan.cv_limit != -1 else 0
            cv_used  = sub.cv_count
        except UserSubscription.DoesNotExist:
            cv_limit, cv_used = 0, 0

        calc = _calc_refund(original.amount, cv_used, cv_limit)
        return Response({
            'transaction_id':  original.id,
            'invoice_number':  original.invoice_number,
            'original_amount': original.amount / 100,
            'currency':        original.currency,
            'cv_used':         cv_used,
            'cv_limit':        cv_limit,
            'usage_pct':       calc['usage_pct'],
            'usage_deduction': calc['usage_deduction'] / 100,
            'processing_fee':  calc['processing_fee'] / 100,
            'refund_amount':   calc['refund_amount'] / 100,
        })


class RefundRequestView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        transaction_id = request.data.get('transaction_id')
        reason       = (request.data.get('reason') or '').strip()
        bank_details = request.data.get('bank_details') or {}
        if not transaction_id:
            return Response({'error': 'transaction_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            original = Transaction.objects.get(
                id=transaction_id,
                user=request.user,
                type=Transaction.PAYMENT,
                status=Transaction.STATUS_PAID,
            )
        except Transaction.DoesNotExist:
            return Response({'error': 'Transaction not found or not eligible.'}, status=status.HTTP_404_NOT_FOUND)

        # Prevent duplicate pending/approved requests for the same transaction
        if RefundRequest.objects.filter(
            transaction=original,
            status__in=(RefundRequest.PENDING, RefundRequest.APPROVED),
        ).exists():
            return Response({'error': 'A refund request for this transaction is already under review.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sub = UserSubscription.objects.select_related('plan').get(user=request.user)
            cv_limit = sub.plan.cv_limit if sub.plan.cv_limit != -1 else 0
            cv_used  = sub.cv_count
        except UserSubscription.DoesNotExist:
            cv_limit, cv_used = 0, 0

        calc = _calc_refund(original.amount, cv_used, cv_limit)

        rr = RefundRequest.objects.create(
            user=request.user,
            transaction=original,
            reason=reason,
            original_amount=original.amount,
            usage_pct=calc['usage_pct'],
            usage_deduction=calc['usage_deduction'],
            processing_fee=calc['processing_fee'],
            refund_amount=calc['refund_amount'],
            currency=original.currency,
            bank_details=bank_details,
        )
        logger.info(
            "RefundRequest #%s created: user=%s tx=%s usage=%s%% refund=$%.2f",
            rr.id, request.user.email, original.id, calc['usage_pct'], calc['refund_amount'] / 100,
        )
        return Response({
            'message':         'Refund request submitted. Our team will review it within 3–5 business days.',
            'refund_request_id': rr.id,
            'reference':       rr.reference,
            'usage_pct':       calc['usage_pct'],
            'usage_deduction': calc['usage_deduction'] / 100,
            'processing_fee':  calc['processing_fee'] / 100,
            'refund_amount':   calc['refund_amount'] / 100,
        }, status=status.HTTP_201_CREATED)
