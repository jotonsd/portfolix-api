from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Plan, UserSubscription


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['email']
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'date_joined']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {'fields': ('first_name', 'last_name', 'avatar', 'contact_number', 'address')}),
        ('Social', {'fields': ('google_id', 'facebook_id')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'first_name', 'last_name', 'password1', 'password2')}),
    )
    search_fields = ['email', 'first_name', 'last_name']
    filter_horizontal = ('groups', 'user_permissions')


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'price', 'cv_limit', 'is_monthly']


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'cv_count', 'period_start', 'expires_at']
    list_select_related = ['user', 'plan']
