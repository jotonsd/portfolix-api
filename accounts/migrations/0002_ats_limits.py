from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='ats_limit',
            field=models.IntegerField(default=2, help_text='-1 = unlimited'),
        ),
        migrations.AddField(
            model_name='usersubscription',
            name='ats_count',
            field=models.IntegerField(default=0),
        ),
    ]
