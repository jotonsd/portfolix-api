import logging

from celery import shared_task

from django.conf import settings
from .services.extractor import extract_text

logger = logging.getLogger('converter')


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def process_cv_task(self, instance_id: int, cv_bytes_hex: str, filename: str):
    from .models import CVUpload

    try:
        instance = CVUpload.objects.get(pk=instance_id)
        try:
            cv_bytes = bytes.fromhex(cv_bytes_hex)
        except ValueError as exc:
            logger.error("Invalid hex payload for id=%s: %s", instance_id, exc)
            raise

        cv_text = extract_text(cv_bytes, filename)

        if not cv_text:
            raise ValueError("No readable text found in the uploaded file.")

        logger.debug("Extracted %d chars from '%s' id=%s", len(cv_text), filename, instance_id)

        if settings.AI_PROVIDER == 'claude':
            from .services.claude_service import generate_portfolio_html
        else:
            from .services.gemini_service import generate_portfolio_html

        logger.info("Using AI provider: %s", settings.AI_PROVIDER)
        html = generate_portfolio_html(cv_text)

        instance.generated_html = html
        instance.status = 'completed'
        instance.save()
        logger.info("Portfolio generated — id=%s", instance_id)

    except CVUpload.DoesNotExist:
        logger.error("CVUpload id=%s not found", instance_id)

    except Exception as exc:
        attempt = self.request.retries + 1
        logger.error("Task failed — id=%s attempt=%s/%s error=%s", instance_id, attempt, self.max_retries + 1, exc, exc_info=True)
        if self.request.retries >= self.max_retries:
            # All attempts exhausted — mark failed and refund the generation slot
            try:
                instance = CVUpload.objects.get(pk=instance_id)
                instance.status = 'failed'
                instance.error_message = str(exc)
                instance.save()
                sub = getattr(instance.user, 'subscription', None)
                if sub and sub.plan.cv_limit != -1:
                    sub.decrement()
                    logger.info("Refunded cv_count for user=%s after permanent failure id=%s", instance.user_id, instance_id)
            except Exception:
                logger.error("Failed to update CVUpload status for id=%s", instance_id, exc_info=True)
        else:
            # Still retrying — keep status as 'processing'
            raise self.retry(exc=exc)
