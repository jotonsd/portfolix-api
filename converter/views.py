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

        instance.cv_file.seek(0)
        cv_bytes_hex = instance.cv_file.read().hex()
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


class JobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_raw = celery_app.control.inspect(timeout=2).active() or {}
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

        reserved_raw = celery_app.control.inspect(timeout=2).reserved() or {}
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

        recent = list(
            CVUpload.objects.filter(user=request.user)
            .values('id', 'status', 'error_message', 'created_at', 'updated_at')
            .order_by('-created_at')[:10]
        )

        return Response({
            "workers": {"active_tasks": active, "queued_tasks": reserved},
            "database": {"summary": db_summary, "recent_jobs": recent},
        })
