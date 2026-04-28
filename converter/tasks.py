import logging

from celery import shared_task

from .services.extractor import extract_text
from .services.claude_service import generate_portfolio_html

logger = logging.getLogger('converter')


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def process_cv_task(self, instance_id: int, cv_bytes_hex: str, filename: str):
    from .models import CVUpload

    try:
        instance = CVUpload.objects.get(pk=instance_id)
        cv_bytes = bytes.fromhex(cv_bytes_hex)

        cv_text = extract_text(cv_bytes, filename)

        if not cv_text:
            raise ValueError("No readable text found in the uploaded file.")

        logger.debug("Extracted %d chars from '%s' id=%s", len(cv_text), filename, instance_id)

        html = generate_portfolio_html(cv_text)

        instance.generated_html = html
        instance.status = 'completed'
        instance.save()
        logger.info("Portfolio generated — id=%s", instance_id)

    except CVUpload.DoesNotExist:
        logger.error("CVUpload id=%s not found", instance_id)

    except Exception as exc:
        logger.error("Task failed — id=%s error=%s", instance_id, exc, exc_info=True)
        try:
            instance = CVUpload.objects.get(pk=instance_id)
            instance.status = 'failed'
            instance.error_message = str(exc)
            instance.save()
        except Exception:
            pass
        raise self.retry(exc=exc)
