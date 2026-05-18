from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_avatar_urlfield'),
    ]

    operations = [
        migrations.CreateModel(
            name='RefundRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('processed', 'Processed')],
                    default='pending', max_length=20,
                )),
                ('original_amount', models.IntegerField()),
                ('usage_pct', models.IntegerField(default=0)),
                ('usage_deduction', models.IntegerField(default=0)),
                ('processing_fee', models.IntegerField(default=0)),
                ('refund_amount', models.IntegerField()),
                ('currency', models.CharField(default='usd', max_length=10)),
                ('bank_details', models.JSONField(blank=True, default=dict)),
                ('admin_note', models.TextField(blank=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('processed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='processed_refunds',
                    to='accounts.user',
                )),
                ('transaction', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refund_requests',
                    to='accounts.transaction',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refund_requests',
                    to='accounts.user',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
