from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_refundrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='stripe_payment_intent_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
