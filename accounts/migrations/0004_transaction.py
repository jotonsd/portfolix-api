from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_usersubscription_stripe_subscription_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.IntegerField(help_text='Amount in cents')),
                ('currency', models.CharField(default='usd', max_length=10)),
                ('plan', models.CharField(blank=True, max_length=50)),
                ('type', models.CharField(choices=[('payment', 'Payment'), ('refund', 'Refund')], default='payment', max_length=20)),
                ('status', models.CharField(default='paid', max_length=50)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('stripe_session_id', models.CharField(blank=True, max_length=255)),
                ('stripe_subscription_id', models.CharField(blank=True, max_length=255)),
                ('stripe_invoice_id', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
