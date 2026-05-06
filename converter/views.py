import logging

from celery.app.control import Control
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from config.celery import app as celery_app
from .models import CVUpload
from .serializers import CVUploadSerializer, CVUploadResultSerializer
from .services.claude_service import _strip_code_fences
from .tasks import process_cv_task

logger = logging.getLogger('converter')


class ConvertCVView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = getattr(request.user, 'subscription', None)
        if not subscription:
            return Response(
                {'error': 'No active plan found. Please contact support.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        can_generate, reason = subscription.can_generate()
        if not can_generate:
            return Response({'error': reason}, status=status.HTTP_403_FORBIDDEN)

        serializer = CVUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        instance = serializer.save(status='processing', user=request.user)
        logger.info("CV upload received — id=%s user=%s file=%s", instance.pk, request.user.email, instance.cv_file.name)

        subscription.increment()

        with instance.cv_file.open('rb') as f:
            cv_bytes_hex = f.read().hex()
        filename = instance.cv_file.name.split('/')[-1]

        process_cv_task.delay(instance.pk, cv_bytes_hex, filename)

        result = CVUploadResultSerializer(instance)
        return Response(result.data, status=status.HTTP_202_ACCEPTED)


class CVDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            instance = CVUpload.objects.get(pk=pk, user=request.user)
        except CVUpload.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = CVUploadResultSerializer(instance)
        return Response(serializer.data)

    def patch(self, request, pk):
        try:
            instance = CVUpload.objects.get(pk=pk, user=request.user)
        except CVUpload.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        html = request.data.get('generated_html')
        if html:
            instance.generated_html = html
            instance.save(update_fields=['generated_html'])

        return Response(CVUploadResultSerializer(instance).data)


class CVPreviewView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            instance = CVUpload.objects.get(pk=pk)
        except CVUpload.DoesNotExist:
            return HttpResponse("Not found.", status=404, content_type="text/plain")

        if instance.status != 'completed' or not instance.generated_html:
            return HttpResponse(
                f"Portfolio not ready. Status: {instance.status}",
                status=400,
                content_type="text/plain",
            )

        html = _strip_code_fences(instance.generated_html)
        return HttpResponse(html, content_type="text/html; charset=utf-8")


class CVDownloadView(APIView):
    """Download the AI-generated portfolio HTML."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            instance = CVUpload.objects.get(pk=pk, user=request.user)
        except CVUpload.DoesNotExist:
            return HttpResponse("Not found.", status=404, content_type="text/plain")

        if instance.status != 'completed' or not instance.generated_html:
            return HttpResponse("Portfolio not ready.", status=400, content_type="text/plain")

        html = _strip_code_fences(instance.generated_html)
        response = HttpResponse(html, content_type="text/html; charset=utf-8")
        response['Content-Disposition'] = f'attachment; filename="portfolio-{pk}.html"'
        return response


class CVFileDownloadView(APIView):
    """Download the original uploaded CV file."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            instance = CVUpload.objects.get(pk=pk, user=request.user)
        except CVUpload.DoesNotExist:
            return HttpResponse("Not found.", status=404, content_type="text/plain")

        if not instance.cv_file:
            return HttpResponse("CV file not available.", status=404, content_type="text/plain")

        import os
        filename = os.path.basename(instance.cv_file.name)
        with instance.cv_file.open('rb') as f:
            content = f.read()

        import mimetypes
        mime, _ = mimetypes.guess_type(filename)
        response = HttpResponse(content, content_type=mime or 'application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class PublicPortfolioView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            instance = CVUpload.objects.get(share_token=token)
        except CVUpload.DoesNotExist:
            return HttpResponse("Portfolio not found.", status=404, content_type="text/plain")

        if instance.status != 'completed' or not instance.generated_html:
            return HttpResponse("Portfolio not ready yet.", status=404, content_type="text/plain")

        html = _strip_code_fences(instance.generated_html)
        return HttpResponse(html, content_type="text/html; charset=utf-8")


class RetryCVView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            instance = CVUpload.objects.get(pk=pk, user=request.user)
        except CVUpload.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if instance.status != 'failed':
            return Response({"error": "Only failed jobs can be retried."}, status=status.HTTP_400_BAD_REQUEST)

        subscription = getattr(request.user, 'subscription', None)
        if not subscription:
            return Response({"error": "No active plan found."}, status=status.HTTP_403_FORBIDDEN)

        # Check limit — retry counts as a new generation attempt
        can_generate, reason = subscription.can_generate()
        if not can_generate:
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)

        # Re-queue — increment now, will be refunded again if it fails
        instance.status = 'processing'
        instance.error_message = ''
        instance.save(update_fields=['status', 'error_message'])

        subscription.increment()

        with instance.cv_file.open('rb') as f:
            cv_bytes_hex = f.read().hex()
        filename = instance.cv_file.name.split('/')[-1]

        process_cv_task.delay(instance.pk, cv_bytes_hex, filename)

        logger.info("CV retry queued — id=%s user=%s", instance.pk, request.user.email)
        result = CVUploadResultSerializer(instance)
        return Response(result.data, status=status.HTTP_202_ACCEPTED)


def _celery_inspect(method: str) -> dict:
    try:
        return getattr(celery_app.control.inspect(timeout=2), method)() or {}
    except Exception:
        logger.warning("Celery broker unreachable, skipping inspect.%s", method)
        return {}


class JobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_raw = _celery_inspect('active')
        active = []
        for worker, tasks in active_raw.items():
            for t in tasks:
                active.append({
                    "task_id": t["id"],
                    "name": t["name"],
                    "worker": worker,
                    "args": t.get("args"),
                    "started": t.get("time_start"),
                    "state": "active",
                })

        reserved_raw = _celery_inspect('reserved')
        reserved = []
        for worker, tasks in reserved_raw.items():
            for t in tasks:
                reserved.append({
                    "task_id": t["id"],
                    "name": t["name"],
                    "worker": worker,
                    "state": "queued",
                })

        db_summary = {
            "processing": CVUpload.objects.filter(user=request.user, status='processing').count(),
            "completed":  CVUpload.objects.filter(user=request.user, status='completed').count(),
            "failed":     CVUpload.objects.filter(user=request.user, status='failed').count(),
        }

        page = max(1, int(request.query_params.get('page', 1)))
        page_size = max(1, min(50, int(request.query_params.get('page_size', 8))))
        qs = CVUpload.objects.filter(user=request.user).order_by('-created_at')
        total = qs.count()
        offset = (page - 1) * page_size
        recent = list(
            qs.values('id', 'share_token', 'status', 'error_message', 'created_at', 'updated_at')[offset:offset + page_size]
        )

        return Response({
            "workers": {"active_tasks": active, "queued_tasks": reserved},
            "database": {
                "summary": db_summary,
                "recent_jobs": recent,
                "pagination": {"page": page, "page_size": page_size, "total": total, "total_pages": max(1, -(-total // page_size))},
            },
        })
