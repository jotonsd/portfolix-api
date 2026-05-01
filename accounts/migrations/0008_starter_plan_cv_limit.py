from django.db import migrations


def update_plans(apps, schema_editor):
    Plan = apps.get_model('accounts', 'Plan')
    Plan.objects.filter(name='starter').update(
        cv_limit=15,
        features=[
            'Shareable portfolio link',
            '15 CV generations per month',
            'AI-powered unique designs',
            'All design styles & animations',
            'HTML download',
            'Priority processing',
            'GitHub Pages deployment (coming soon)',
            'cPanel deployment (coming soon)',
        ],
    )
    Plan.objects.filter(name='pro').update(
        cv_limit=40,
        features=[
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
    )


def reverse_plans(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_plan_features_update'),
    ]

    operations = [
        migrations.RunPython(update_plans, reverse_plans),
    ]
