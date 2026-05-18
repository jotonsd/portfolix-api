from django.urls import path
from .views import (
    RegisterView, LoginView, GoogleLoginView, FacebookLoginView,
    ProfileView, PlanListView, TokenRefreshView,
    CreateCheckoutSessionView, StripeWebhookView, OnboardingView,
    RefundEstimateView, RefundRequestView,
)
from .admin_views import (
    AdminDashboardView, AdminUserListView, AdminUserDetailView,
    AdminRevenueView, AdminLedgerView, UserBillingView,
    AdminStaffView, AdminStaffDetailView,
    AdminRefundRequestListView, AdminRefundRequestDetailView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('google/', GoogleLoginView.as_view(), name='google-login'),
    path('facebook/', FacebookLoginView.as_view(), name='facebook-login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('plans/', PlanListView.as_view(), name='plan-list'),
    path('onboarding/', OnboardingView.as_view(), name='onboarding'),

    path('stripe/checkout/', CreateCheckoutSessionView.as_view(), name='stripe-checkout'),
    path('stripe/webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('refund/estimate/', RefundEstimateView.as_view(), name='refund-estimate'),
    path('refund/request/', RefundRequestView.as_view(), name='refund-request'),

    path('admin/dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/revenue/', AdminRevenueView.as_view(), name='admin-revenue'),
    path('admin/ledger/', AdminLedgerView.as_view(), name='admin-ledger'),
    path('admin/staff/', AdminStaffView.as_view(), name='admin-staff'),
    path('admin/staff/<int:pk>/', AdminStaffDetailView.as_view(), name='admin-staff-detail'),
    path('admin/refund-requests/', AdminRefundRequestListView.as_view(), name='admin-refund-requests'),
    path('admin/refund-requests/<int:pk>/', AdminRefundRequestDetailView.as_view(), name='admin-refund-request-detail'),
    path('billing/', UserBillingView.as_view(), name='user-billing'),
]
