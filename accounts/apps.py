from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_plans, sender=self)


def _seed_plans(sender, **kwargs):
    from .models import Plan
    plans = [
        {
            'name': Plan.FREE,
            'display_name': 'Free',
            'price': 0,
            'cv_limit': 1,
            'is_monthly': False,
            'features': [
                '1 CV generation (lifetime)',
                'AI-powered unique design',
                'Tailwind CSS portfolio',
                'HTML download',
            ],
        },
        {
            'name': Plan.STARTER,
            'display_name': 'Starter',
            'price': 19,
            'cv_limit': 15,
            'is_monthly': True,
            'features': [
                '15 CV generations per month',
                'AI-powered unique designs',
                'All design styles & animations',
                'HTML download',
                'GitHub Pages deployment (coming soon)',
                'cPanel deployment (coming soon)',
                'Priority processing',
            ],
        },
        {
            'name': Plan.PRO,
            'display_name': 'Pro',
            'price': 49,
            'cv_limit': -1,
            'is_monthly': True,
            'features': [
                'Unlimited CV generations',
                'AI-powered unique designs',
                'All design styles & animations',
                'HTML download',
                'GitHub Pages auto-deploy (coming soon)',
                'AWS S3 auto-deploy (coming soon)',
                'cPanel auto-deploy (coming soon)',
                'Priority processing',
                'Early access to new features',
            ],
        },
    ]
    for data in plans:
        name = data.pop('name')
        Plan.objects.update_or_create(name=name, defaults=data)
