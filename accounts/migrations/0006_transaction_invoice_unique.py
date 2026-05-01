from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_transaction_session_unique'),
    ]

    operations = [
        # Step 1: allow NULL first
        migrations.AlterField(
            model_name='transaction',
            name='stripe_invoice_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        # Step 2: convert empty strings to NULL
        migrations.RunSQL(
            sql="UPDATE accounts_transaction SET stripe_invoice_id = NULL WHERE stripe_invoice_id = ''",
            reverse_sql="UPDATE accounts_transaction SET stripe_invoice_id = '' WHERE stripe_invoice_id IS NULL",
        ),
        # Step 3: add unique constraint
        migrations.AlterField(
            model_name='transaction',
            name='stripe_invoice_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
    ]
