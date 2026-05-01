from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_transaction'),
    ]

    operations = [
        # Nullify blank stripe_session_id so unique constraint works
        migrations.RunSQL(
            sql="UPDATE accounts_transaction SET stripe_session_id = NULL WHERE stripe_session_id = ''",
            reverse_sql="UPDATE accounts_transaction SET stripe_session_id = '' WHERE stripe_session_id IS NULL",
        ),
        # Remove duplicate rows, keeping the oldest (lowest id) per session
        migrations.RunSQL(
            sql="""
                DELETE FROM accounts_transaction
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM accounts_transaction
                    WHERE stripe_session_id IS NOT NULL
                    GROUP BY stripe_session_id
                )
                AND stripe_session_id IS NOT NULL
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='transaction',
            name='stripe_session_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
    ]
