import uuid
from django.db import migrations, models


def gen_tokens(apps, schema_editor):
    CVUpload = apps.get_model('converter', 'CVUpload')
    for row in CVUpload.objects.all():
        row.share_token = uuid.uuid4()
        row.save(update_fields=['share_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('converter', '0002_cvupload_user'),
    ]

    operations = [
        # Add non-unique first so existing rows get a value
        migrations.AddField(
            model_name='cvupload',
            name='share_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        # Backfill each row with a unique UUID
        migrations.RunPython(gen_tokens, migrations.RunPython.noop),
        # Now enforce uniqueness
        migrations.AlterField(
            model_name='cvupload',
            name='share_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
