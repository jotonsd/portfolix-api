from django.db import migrations

PLAN_DATA = [
    {
        'name': 'free',
        'display_name': 'Free',
        'price': '0.00',
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
        'name': 'starter',
        'display_name': 'Starter',
        'price': '19.00',
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
        'name': 'pro',
        'display_name': 'Pro',
        'price': '49.00',
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


def update_plans(apps, schema_editor):
    Plan = apps.get_model('accounts', 'Plan')
    for data in PLAN_DATA:
        Plan.objects.update_or_create(
            name=data['name'],
            defaults={
                'display_name': data['display_name'],
                'price': data['price'],
                'cv_limit': data['cv_limit'],
                'is_monthly': data['is_monthly'],
                'features': data['features'],
            },
        )


def reverse_plans(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_transaction_invoice_unique'),
    ]

    operations = [
        migrations.RunPython(update_plans, reverse_plans),
    ]
