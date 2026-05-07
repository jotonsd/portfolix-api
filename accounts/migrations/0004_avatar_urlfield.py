from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_social_avatar'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='social_avatar',
        ),
        migrations.AlterField(
            model_name='user',
            name='avatar',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
