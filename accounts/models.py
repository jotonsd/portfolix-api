from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import F
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('user_type', 'admin')
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    ADMIN = 'admin'
    USER = 'user'
    USER_TYPE_CHOICES = [(ADMIN, 'Admin'), (USER, 'User')]

    username = None
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default=USER)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    google_id = models.CharField(max_length=128, blank=True)
    facebook_id = models.CharField(max_length=128, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    def __str__(self):
        return self.email


class Plan(models.Model):
    FREE = 'free'
    STARTER = 'starter'
    PRO = 'pro'

    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cv_limit = models.IntegerField(help_text='-1 = unlimited')
    is_monthly = models.BooleanField(default=False, help_text='If True, limit resets monthly')
    features = models.JSONField(default=list)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return self.display_name


class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    cv_count = models.IntegerField(default=0)
    period_start = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} — {self.plan.name}"

    def reset_if_new_month(self):
        if not self.plan.is_monthly:
            return
        now = timezone.now()
        if now.month != self.period_start.month or now.year != self.period_start.year:
            self.cv_count = 0
            self.period_start = now
            self.save(update_fields=['cv_count', 'period_start'])

    def can_generate(self):
        if self.plan.cv_limit == -1:
            return True, None
        self.reset_if_new_month()
        if self.cv_count >= self.plan.cv_limit:
            return False, f"You have reached your {self.plan.display_name} plan limit of {self.plan.cv_limit} CV generation(s). Please upgrade your plan."
        return True, None

    def increment(self):
        # Atomic DB-level increment — prevents race condition under concurrent requests
        UserSubscription.objects.filter(pk=self.pk).update(cv_count=F('cv_count') + 1)
        self.refresh_from_db(fields=['cv_count'])
