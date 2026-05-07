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
            'ats_limit': 2,
            'is_monthly': False,
            'features': [
                'CV Builder (2 templates)',
                'ATS Score – Basic (2 analyses)',
                'Export PDF',
            ],
        },
        {
            'name': Plan.STARTER,
            'display_name': 'Starter',
            'price': 9,
            'cv_limit': 15,
            'ats_limit': 20,
            'is_monthly': True,
            'features': [
                'CV Builder (all templates)',
                'ATS Score – Detailed (20/month)',
                'ATS Improvements',
                'Export PDF',
                'Portfolio Generation',
                'GitHub Pages Deploy',
            ],
        },
        {
            'name': Plan.PRO,
            'display_name': 'Pro',
            'price': 19,
            'cv_limit': -1,
            'ats_limit': -1,
            'is_monthly': True,
            'features': [
                'CV Builder (all + custom)',
                'ATS Score – Detailed',
                'ATS Improvements',
                'Export PDF',
                'Portfolio Generation',
                'GitHub Pages Deploy',
                'AWS Deploy',
                'Cover Letter',
                'LinkedIn Bio',
                'GitHub README',
                'Custom Domain',
                'Analytics',
                'Remove Branding',
            ],
        },
    ]
    for data in plans:
        name = data.pop('name')
        Plan.objects.update_or_create(name=name, defaults=data)
