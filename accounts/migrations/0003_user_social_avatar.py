from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_ats_limits'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='social_avatar',
            field=models.URLField(blank=True, default='', help_text='Profile picture URL from social login'),
        ),
    ]
