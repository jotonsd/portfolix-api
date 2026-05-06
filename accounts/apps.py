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
                'Shareable portfolio link',
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
                'Shareable portfolio link',
                '15 CV generations per month',
                'AI-powered unique designs',
                'All design styles & animations',
                'HTML download',
                'Priority processing',
                'GitHub Pages deployment (coming soon)',
                'cPanel deployment (coming soon)',
            ],
        },
        {
            'name': Plan.PRO,
            'display_name': 'Pro',
            'price': 49,
            'cv_limit': 40,
            'is_monthly': True,
            'features': [
                'Shareable portfolio link',
                '40 CV generations per month',
                'AI-powered unique designs',
                'All design styles & animations',
                'HTML download',
                'Priority processing',
                'GitHub Pages auto-deploy (coming soon)',
                'AWS S3 auto-deploy (coming soon)',
                'cPanel auto-deploy (coming soon)',
                'Early access to new features',
            ],
        },
    ]
    for data in plans:
        name = data.pop('name')
        Plan.objects.update_or_create(name=name, defaults=data)
