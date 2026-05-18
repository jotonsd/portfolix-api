import logging
import stripe
from django.conf import settings as django_settings
from django.contrib.auth.hashers import make_password

stripe.api_key = getattr(django_settings, 'STRIPE_SECRET_KEY', '')
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.parsers import JSONParser

from .models import User, Plan, UserSubscription, Transaction, RefundRequest
from converter.models import CVUpload

logger = logging.getLogger('accounts')


class IsAdminType(BasePermission):
    """Only superadmins (user_type=admin)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == 'admin')


class IsAdminOrStaff(BasePermission):
    """Admin or staff — read/manage the admin panel."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type in ('admin', 'staff'))


class AdminDashboardView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        now = timezone.now()
        last_30 = now - timedelta(days=30)
        last_7 = now - timedelta(days=7)

        total_users = User.objects.count()
        new_users_30d = User.objects.filter(date_joined__gte=last_30).count()
        new_users_7d = User.objects.filter(date_joined__gte=last_7).count()

        total_cvs = CVUpload.objects.count()
        cvs_30d = CVUpload.objects.filter(created_at__gte=last_30).count()
        cvs_7d = CVUpload.objects.filter(created_at__gte=last_7).count()
        completed_cvs = CVUpload.objects.filter(status='completed').count()
        failed_cvs = CVUpload.objects.filter(status='failed').count()

        plan_breakdown = list(
            UserSubscription.objects.values('plan__name', 'plan__display_name')
            .annotate(count=Count('id'))
            .order_by('plan__price')
        )

        return Response({
            'users': {
                'total': total_users,
                'new_last_7_days': new_users_7d,
                'new_last_30_days': new_users_30d,
            },
            'cv_generations': {
                'total': total_cvs,
                'completed': completed_cvs,
                'failed': failed_cvs,
                'last_7_days': cvs_7d,
                'last_30_days': cvs_30d,
            },
            'plans': plan_breakdown,
        })


class AdminUserListView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        search = request.query_params.get('search', '')
        plan = request.query_params.get('plan', '')

        qs = User.objects.filter(user_type=User.USER).select_related('subscription__plan').prefetch_related('cv_uploads')

        if search:
            qs = qs.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        if plan:
            qs = qs.filter(subscription__plan__name=plan)

        users = []
        for user in qs.order_by('-date_joined')[:100]:
            sub = getattr(user, 'subscription', None)
            users.append({
                'id': user.id,
                'full_name': f"{user.first_name} {user.last_name}".strip(),
                'email': user.email,
                'avatar': user.avatar or None,
                'is_active': user.is_active,
                'date_joined': user.date_joined,
                'plan': sub.plan.name if sub else 'free',
                'plan_display': sub.plan.display_name if sub else 'Free',
                'cv_count': sub.cv_count if sub else 0,
                'cv_limit': sub.plan.cv_limit if sub else 1,
                'total_cvs': user.cv_uploads.count(),
                'completed_cvs': user.cv_uploads.filter(status='completed').count(),
            })

        return Response({'users': users, 'total': len(users)})


class AdminUserDetailView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request, pk):
        try:
            user = User.objects.select_related('subscription__plan').get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'Not found.'}, status=404)

        sub = getattr(user, 'subscription', None)
        cvs = list(
            CVUpload.objects.filter(user=user)
            .values('id', 'status', 'created_at', 'updated_at', 'error_message')
            .order_by('-created_at')[:20]
        )

        return Response({
            'id': user.id,
            'full_name': f"{user.first_name} {user.last_name}".strip(),
            'email': user.email,
            'avatar': user.avatar or None,
            'contact_number': user.contact_number,
            'address': user.address,
            'is_active': user.is_active,
            'user_type': user.user_type,
            'date_joined': user.date_joined,
            'plan': sub.plan.name if sub else 'free',
            'plan_display': sub.plan.display_name if sub else 'Free',
            'cv_count': sub.cv_count if sub else 0,
            'cv_limit': sub.plan.cv_limit if sub else 1,
            'recent_cvs': cvs,
        })

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'Not found.'}, status=404)

        if 'is_active' in request.data:
            user.is_active = request.data['is_active']
            user.save(update_fields=['is_active'])

        if 'plan' in request.data:
            try:
                plan = Plan.objects.get(name=request.data['plan'])
                sub, _ = UserSubscription.objects.get_or_create(user=user, defaults={'plan': plan})
                if sub.plan != plan:
                    sub.plan = plan
                    sub.cv_count = 0
                    sub.save()
            except Plan.DoesNotExist:
                return Response({'error': 'Invalid plan.'}, status=400)

        return Response({'success': True})


def _tx_to_dict(tx, include_user=False):
    d = {
        'id': tx.id,
        'invoice_number': tx.invoice_number,
        'amount': tx.amount,
        'amount_display': round(tx.amount / 100, 2),
        'currency': tx.currency.upper(),
        'plan': tx.plan,
        'type': tx.type,
        'status': tx.status,
        'description': tx.description,
        'stripe_session_id': tx.stripe_session_id,
        'created_at': tx.created_at,
    }
    if include_user:
        d['user_email'] = tx.user.email if tx.user else '—'
        d['user_id'] = tx.user.id if tx.user else None
    return d


class AdminRevenueView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        now = timezone.now()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_30 = now - timedelta(days=30)
        last_7 = now - timedelta(days=7)

        payments = Transaction.objects.filter(type=Transaction.PAYMENT, status=Transaction.STATUS_PAID)
        refunds = Transaction.objects.filter(type=Transaction.REFUND)

        total_income = payments.aggregate(s=Sum('amount'))['s'] or 0
        total_refunds = refunds.aggregate(s=Sum('amount'))['s'] or 0
        mrr = payments.filter(created_at__gte=first_of_month).aggregate(s=Sum('amount'))['s'] or 0
        income_30d = payments.filter(created_at__gte=last_30).aggregate(s=Sum('amount'))['s'] or 0
        income_7d = payments.filter(created_at__gte=last_7).aggregate(s=Sum('amount'))['s'] or 0

        by_plan = list(
            payments.values('plan')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total')
        )
        for row in by_plan:
            row['total_display'] = round(row['total'] / 100, 2)

        monthly = []
        for i in range(11, -1, -1):
            month_offset = (now.month - 1 - i) % 12 + 1
            year_offset = now.year + ((now.month - 1 - i) // 12)
            start = now.replace(year=year_offset, month=month_offset, day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
            amt = payments.filter(created_at__gte=start, created_at__lt=end).aggregate(s=Sum('amount'))['s'] or 0
            monthly.append({
                'month': start.strftime('%b %Y'),
                'amount': round(amt / 100, 2),
            })

        return Response({
            'total_income': round(total_income / 100, 2),
            'total_refunds': round(total_refunds / 100, 2),
            'net_revenue': round((total_income - total_refunds) / 100, 2),
            'mrr': round(mrr / 100, 2),
            'income_last_30d': round(income_30d / 100, 2),
            'income_last_7d': round(income_7d / 100, 2),
            'total_transactions': payments.count(),
            'by_plan': by_plan,
            'monthly_chart': monthly,
        })


class AdminLedgerView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = max(1, min(50, int(request.query_params.get('page_size', 20))))
        plan_filter = request.query_params.get('plan', '')
        search = request.query_params.get('search', '')

        qs = Transaction.objects.select_related('user')
        if plan_filter:
            qs = qs.filter(plan=plan_filter)
        if search:
            qs = qs.filter(Q(user__email__icontains=search) | Q(description__icontains=search))

        total = qs.count()
        offset = (page - 1) * page_size
        txs = qs[offset:offset + page_size]

        return Response({
            'results': [_tx_to_dict(tx, include_user=True) for tx in txs],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': max(1, -(-total // page_size)),
            },
        })


def _rr_to_dict(rr):
    return {
        'id':               rr.id,
        'reference':        rr.reference,
        'transaction_id':   rr.transaction_id,
        'transaction_invoice': rr.transaction.invoice_number,
        'original_amount':  rr.original_amount / 100,
        'usage_pct':        rr.usage_pct,
        'usage_deduction':  rr.usage_deduction / 100,
        'processing_fee':   rr.processing_fee / 100,
        'refund_amount':    rr.refund_amount / 100,
        'currency':         rr.currency,
        'reason':           rr.reason,
        'bank_details':     rr.bank_details,
        'status':           rr.status,
        'admin_note':       rr.admin_note,
        'created_at':       rr.created_at,
    }


class UserBillingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        txs = Transaction.objects.filter(user=request.user)
        refund_requests = RefundRequest.objects.filter(user=request.user).select_related('transaction')
        return Response({
            'results': [_tx_to_dict(tx) for tx in txs],
            'total_paid': round((txs.filter(type=Transaction.PAYMENT, status=Transaction.STATUS_PAID).aggregate(s=Sum('amount'))['s'] or 0) / 100, 2),
            'refund_requests': [_rr_to_dict(rr) for rr in refund_requests],
        })


class AdminRefundRequestListView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        status_filter = request.query_params.get('status', '')
        qs = RefundRequest.objects.select_related('user', 'transaction')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response({
            'results': [{**_rr_to_dict(rr), 'user_email': rr.user.email, 'user_id': rr.user_id} for rr in qs],
            'total': qs.count(),
        })


class AdminRefundRequestDetailView(APIView):
    permission_classes = [IsAdminOrStaff]
    parser_classes = [JSONParser]

    def patch(self, request, pk):
        try:
            rr = RefundRequest.objects.select_related('user', 'transaction').get(pk=pk)
        except RefundRequest.DoesNotExist:
            return Response({'error': 'Not found.'}, status=404)

        new_status = request.data.get('status')
        admin_note = (request.data.get('admin_note') or '').strip()

        # Amount override (only allowed on pending/approved, and only before processing)
        if 'refund_amount' in request.data:
            if rr.status not in (RefundRequest.PENDING, RefundRequest.APPROVED):
                return Response({'error': 'Cannot edit amount on a processed or rejected request.'}, status=400)
            try:
                new_cents = int(round(float(request.data['refund_amount']) * 100))
            except (ValueError, TypeError):
                return Response({'error': 'Invalid refund_amount.'}, status=400)
            if new_cents < 0 or new_cents > rr.original_amount:
                return Response({
                    'error': f'Amount must be between $0.00 and ${rr.original_amount / 100:.2f}.'
                }, status=400)
            rr.refund_amount = new_cents
            rr.save(update_fields=['refund_amount'])
            return Response(_rr_to_dict(rr))

        allowed = {
            RefundRequest.PENDING:   [RefundRequest.APPROVED, RefundRequest.REJECTED],
            RefundRequest.APPROVED:  [RefundRequest.PROCESSED, RefundRequest.REJECTED],
        }
        if new_status and new_status not in allowed.get(rr.status, []):
            return Response({'error': f'Cannot transition from {rr.status} to {new_status}.'}, status=400)

        if admin_note:
            rr.admin_note = admin_note

        if new_status:
            rr.status = new_status
            if new_status in (RefundRequest.APPROVED, RefundRequest.REJECTED, RefundRequest.PROCESSED):
                from django.utils import timezone as tz
                rr.processed_by = request.user
                rr.processed_at = tz.now()

            # When processed → attempt Stripe auto-refund then create ledger entry
            if new_status == RefundRequest.PROCESSED:
                stripe_refund_id = ''
                refund_method = (rr.bank_details or {}).get('method', 'original_card')

                if refund_method == 'original_card':
                    payment_intent_id = None
                    sub_id = rr.transaction.stripe_subscription_id

                    # 1. Fastest path: stored directly on the transaction (new transactions)
                    if rr.transaction.stripe_payment_intent_id:
                        payment_intent_id = rr.transaction.stripe_payment_intent_id
                        logger.info("Using stored payment_intent %s for rr=%s", payment_intent_id, rr.id)

                    try:
                        # 2. Lookup via subscription's initial invoice (older transactions).
                        # Pin to API 2024-04-10 — Stripe 2025-07-30.basil removed payment_intent
                        # from invoice responses, but the older version still returns it.
                        if not payment_intent_id and sub_id:
                            invoices = stripe.Invoice.list(
                                subscription=sub_id,
                                limit=10,
                                expand=['data.payment_intent'],
                                stripe_version='2024-04-10',
                            )
                            for inv in invoices.data:
                                if getattr(inv, 'billing_reason', None) == 'subscription_create':
                                    pi = getattr(inv, 'payment_intent', None)
                                    if pi:
                                        payment_intent_id = pi if isinstance(pi, str) else pi.id
                                        # Cache it so we don't have to look it up again
                                        rr.transaction.stripe_payment_intent_id = payment_intent_id
                                        rr.transaction.save(update_fields=['stripe_payment_intent_id'])
                                    break

                        # 3. Fallback: direct payment_intent on session (one-time payments)
                        if not payment_intent_id and rr.transaction.stripe_session_id:
                            session = stripe.checkout.Session.retrieve(
                                rr.transaction.stripe_session_id,
                                expand=['payment_intent'],
                            )
                            pi = getattr(session, 'payment_intent', None)
                            if pi:
                                payment_intent_id = pi if isinstance(pi, str) else pi.id

                        if not payment_intent_id:
                            logger.error("No payment_intent found for rr=%s sub=%s", rr.id, sub_id)
                            return Response(
                                {'error': 'Could not locate the original Stripe payment intent. Process this refund manually.'},
                                status=400,
                            )

                        stripe_refund = stripe.Refund.create(
                            payment_intent=payment_intent_id,
                            amount=rr.refund_amount,
                            reason='requested_by_customer',
                            metadata={
                                'refund_request_id': str(rr.id),
                                'user_id': str(rr.user_id),
                            },
                        )
                        stripe_refund_id = stripe_refund.id  # attribute access, not .get()
                        logger.info(
                            "Stripe refund created: %s rr=%s pi=%s amount=$%.2f",
                            stripe_refund_id, rr.id, payment_intent_id, rr.refund_amount / 100,
                        )

                    except stripe.error.StripeError as e:
                        logger.error("Stripe refund failed for rr=%s: %s", rr.id, e)
                        return Response({'error': f'Stripe error: {str(e)}'}, status=400)
                    except Exception as e:
                        logger.error("Unexpected refund error for rr=%s: %s", rr.id, e, exc_info=True)
                        return Response({'error': f'Unexpected error: {str(e)}'}, status=500)

                desc = f"Refund processed for {rr.transaction.invoice_number} (ref: {rr.reference})"
                if stripe_refund_id:
                    desc += f" · Stripe: {stripe_refund_id}"
                elif refund_method != 'original_card':
                    desc += f" · via {refund_method.replace('_', ' ')}"

                Transaction.objects.create(
                    user=rr.user,
                    amount=rr.refund_amount,
                    currency=rr.currency,
                    plan=rr.transaction.plan,
                    type=Transaction.REFUND,
                    status=Transaction.STATUS_PAID,
                    description=desc,
                )
                logger.info("Refund processed: rr=%s user=%s amount=$%.2f method=%s", rr.id, rr.user.email, rr.refund_amount / 100, refund_method)

                # Cancel the Stripe subscription and downgrade user to free plan
                sub_id = rr.transaction.stripe_subscription_id
                if sub_id:
                    try:
                        stripe.Subscription.cancel(sub_id)
                        logger.info("Stripe subscription %s cancelled for rr=%s", sub_id, rr.id)
                    except stripe.error.StripeError as e:
                        logger.warning("Could not cancel Stripe sub %s (may already be cancelled): %s", sub_id, e)

                try:
                    free_plan = Plan.objects.get(name=Plan.FREE)
                    user_sub = UserSubscription.objects.get(user=rr.user)
                    user_sub.plan = free_plan
                    user_sub.stripe_subscription_id = ''
                    user_sub.cv_count = 0
                    user_sub.period_start = timezone.now()
                    user_sub.expires_at = None
                    user_sub.save(update_fields=['plan', 'stripe_subscription_id', 'cv_count', 'period_start', 'expires_at'])
                    logger.info("Downgraded user %s to free after refund rr=%s", rr.user.email, rr.id)
                except (Plan.DoesNotExist, UserSubscription.DoesNotExist) as e:
                    logger.warning("Could not downgrade user %s after refund: %s", rr.user.email, e)

        rr.save()
        return Response(_rr_to_dict(rr))


class AdminStaffView(APIView):
    """List all staff/admin users and create new staff (admin only)."""
    permission_classes = [IsAdminType]
    parser_classes = [JSONParser]

    def get(self, request):
        qs = User.objects.filter(user_type__in=('admin', 'staff')).order_by('-date_joined')
        staff = []
        for u in qs:
            staff.append({
                'id': u.id,
                'full_name': f"{u.first_name} {u.last_name}".strip(),
                'email': u.email,
                'user_type': u.user_type,
                'is_active': u.is_active,
                'date_joined': u.date_joined,
                'avatar': u.avatar or None,
            })
        return Response({'staff': staff, 'total': len(staff)})

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        password = request.data.get('password', '').strip()

        if not email or not first_name or not password:
            return Response({'error': 'email, first_name and password are required.'}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({'error': 'A user with this email already exists.'}, status=400)
        if len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters.'}, status=400)

        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            user_type=User.STAFF,
            is_active=True,
            password=make_password(password),
        )
        logger.info("Admin %s created staff user %s", request.user.email, email)
        return Response({
            'id': user.id,
            'full_name': f"{user.first_name} {user.last_name}".strip(),
            'email': user.email,
            'user_type': user.user_type,
            'is_active': user.is_active,
            'date_joined': user.date_joined,
        }, status=201)


class AdminStaffDetailView(APIView):
    """Toggle active status or delete a staff member (admin only)."""
    permission_classes = [IsAdminType]
    parser_classes = [JSONParser]

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk, user_type__in=('admin', 'staff'))
        except User.DoesNotExist:
            return Response({'error': 'Not found.'}, status=404)
        if user.pk == request.user.pk:
            return Response({'error': 'Cannot modify your own account here.'}, status=400)
        if 'is_active' in request.data:
            user.is_active = request.data['is_active']
            user.save(update_fields=['is_active'])
        return Response({'success': True})

    def delete(self, request, pk):
        try:
            user = User.objects.get(pk=pk, user_type='staff')
        except User.DoesNotExist:
            return Response({'error': 'Staff member not found.'}, status=404)
        if user.pk == request.user.pk:
            return Response({'error': 'Cannot delete yourself.'}, status=400)
        user.delete()
        logger.info("Admin %s deleted staff user %s", request.user.email, user.email)
        return Response({'success': True})
