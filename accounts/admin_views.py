import logging
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework.parsers import JSONParser

from .models import User, Plan, UserSubscription
from converter.models import CVUpload

logger = logging.getLogger('accounts')


class IsAdminType(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.user_type == 'admin')


class AdminDashboardView(APIView):
    permission_classes = [IsAdminType]

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
    permission_classes = [IsAdminType]

    def get(self, request):
        search = request.query_params.get('search', '')
        plan = request.query_params.get('plan', '')

        qs = User.objects.select_related('subscription__plan').prefetch_related('cv_uploads')

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
                'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None,
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
    permission_classes = [IsAdminType]

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
            'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None,
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
