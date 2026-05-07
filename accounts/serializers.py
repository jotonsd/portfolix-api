from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from .models import User, Plan, UserSubscription


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'password',
                  'contact_number', 'address']
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'contact_number': {'required': False},
            'address': {'required': False},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        if not user.is_active:
            raise serializers.ValidationError('Account is disabled.')
        data['user'] = user
        return data


class SocialAuthSerializer(serializers.Serializer):
    access_token = serializers.CharField()


class ProfileSerializer(serializers.ModelSerializer):
    plan            = serializers.SerializerMethodField()
    cv_count        = serializers.SerializerMethodField()
    cv_limit        = serializers.SerializerMethodField()
    ats_count       = serializers.SerializerMethodField()
    ats_limit       = serializers.SerializerMethodField()
    plan_expires_at = serializers.SerializerMethodField()
    avatar          = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'avatar',
                  'contact_number', 'address', 'plan', 'cv_count', 'cv_limit',
                  'ats_count', 'ats_limit', 'plan_expires_at',
                  'user_type', 'date_joined', 'onboarding_completed', 'profession', 'job_hunting']
        read_only_fields = ['id', 'email', 'date_joined', 'plan', 'cv_count', 'cv_limit',
                            'ats_count', 'ats_limit', 'plan_expires_at', 'user_type']

    def get_avatar(self, obj):
        return obj.avatar or None

    def get_plan(self, obj):
        if obj.user_type in (User.ADMIN, User.STAFF):
            return None
        try:
            return obj.subscription.plan.name
        except ObjectDoesNotExist:
            return 'free'

    def get_cv_count(self, obj):
        if obj.user_type in (User.ADMIN, User.STAFF):
            return None
        try:
            return obj.subscription.cv_count
        except ObjectDoesNotExist:
            return 0

    def get_cv_limit(self, obj):
        if obj.user_type in (User.ADMIN, User.STAFF):
            return None
        try:
            limit = obj.subscription.plan.cv_limit
            return limit if limit != -1 else 'unlimited'
        except ObjectDoesNotExist:
            return 1

    def get_ats_count(self, obj):
        if obj.user_type in (User.ADMIN, User.STAFF):
            return None
        try:
            return obj.subscription.ats_count
        except ObjectDoesNotExist:
            return 0

    def get_ats_limit(self, obj):
        if obj.user_type in (User.ADMIN, User.STAFF):
            return None
        try:
            limit = obj.subscription.plan.ats_limit
            return limit if limit != -1 else 'unlimited'
        except ObjectDoesNotExist:
            return 2

    def get_plan_expires_at(self, obj):
        if obj.user_type in (User.ADMIN, User.STAFF):
            return None
        try:
            return obj.subscription.expires_at
        except ObjectDoesNotExist:
            return None


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'display_name', 'price', 'cv_limit', 'is_monthly', 'features']
