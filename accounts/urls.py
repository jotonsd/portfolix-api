from django.urls import path
from .views import (
    RegisterView, LoginView, GoogleLoginView, FacebookLoginView,
    ProfileView, PlanListView, TokenRefreshView,
)
from .admin_views import AdminDashboardView, AdminUserListView, AdminUserDetailView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('google/', GoogleLoginView.as_view(), name='google-login'),
    path('facebook/', FacebookLoginView.as_view(), name='facebook-login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('plans/', PlanListView.as_view(), name='plan-list'),

    path('admin/dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
]
