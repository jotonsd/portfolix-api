import logging

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from django.conf import settings as django_settings
from .models import CVUpload, CVBuilderJob
from .serializers import CVUploadSerializer, CVUploadResultSerializer
from .services.claude_service import _strip_code_fences
from .services.extractor import extract_text
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

        if subscription.plan.name == 'free':
            return Response(
                {'error': 'Portfolio Generation is not available on the Free plan. Please upgrade to Starter or Pro.'},
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


_BRANDING_BADGE = (
    '<div style="position:fixed;bottom:16px;right:16px;z-index:9999;">'
    '<a href="https://portfolix.co" target="_blank" rel="noreferrer" '
    'style="display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#6366f1,#8b5cf6);'
    'color:#fff;padding:6px 14px;border-radius:20px;font-size:11px;font-weight:700;font-family:system-ui,sans-serif;'
    'text-decoration:none;box-shadow:0 4px 14px rgba(99,102,241,0.45);letter-spacing:.02em;">'
    '&#9889; Made with Portfolix</a></div>'
)


def _inject_branding(html: str) -> str:
    if '</body>' in html:
        return html.replace('</body>', f'{_BRANDING_BADGE}</body>', 1)
    return html + _BRANDING_BADGE


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
        try:
            if instance.user.subscription.plan.name == 'free':
                html = _inject_branding(html)
        except Exception:
            pass
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

        if subscription.plan.name == 'free':
            return Response(
                {'error': 'Portfolio Generation requires Starter or Pro plan.'},
                status=status.HTTP_403_FORBIDDEN,
            )

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


class JobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page      = max(1, int(request.query_params.get('page', 1)))
        page_size = max(1, min(50, int(request.query_params.get('page_size', 8))))
        qs        = CVUpload.objects.filter(user=request.user).order_by('-created_at')
        total     = qs.count()
        offset    = (page - 1) * page_size
        recent    = list(
            qs.values('id', 'share_token', 'status', 'error_message', 'created_at', 'updated_at')[offset:offset + page_size]
        )

        return Response({
            "database": {
                "recent_jobs": recent,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": max(1, -(-total // page_size)),
                },
            },
        })


# ── CV Builder (template-based, client-side generation) ─────────────────────


class CVBuilderListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        jobs = CVBuilderJob.objects.filter(user=request.user).values(
            'id', 'template', 'form_data', 'created_at', 'updated_at'
        )
        return Response(list(jobs))

    def post(self, request):
        template = request.data.get('template', 'classic')
        form_data = request.data.get('form_data', {})
        if template not in dict(CVBuilderJob.TEMPLATE_CHOICES):
            return Response({'error': 'Invalid template.'}, status=status.HTTP_400_BAD_REQUEST)

        TEMPLATE_MIN_PLAN = {
            'classic': 'free', 'minimal': 'free',
            'modern': 'starter', 'creative': 'starter', 'developer': 'starter',
            'custom': 'pro',
        }
        PLAN_ORDER = ['free', 'starter', 'pro']
        subscription = getattr(request.user, 'subscription', None)
        user_plan = subscription.plan.name if subscription else 'free'

        if user_plan == 'free':
            existing_count = CVBuilderJob.objects.filter(user=request.user).count()
            if existing_count >= 1:
                return Response(
                    {'error': 'Free plan users can only create 1 CV. Upgrade to Starter or Pro to create more.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        required = TEMPLATE_MIN_PLAN.get(template, 'starter')
        if PLAN_ORDER.index(user_plan) < PLAN_ORDER.index(required):
            return Response(
                {'error': f'The {template} template requires the {required.title()} plan or above.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        job = CVBuilderJob.objects.create(user=request.user, template=template, form_data=form_data)
        return Response({'id': job.pk, 'template': job.template, 'created_at': job.created_at}, status=status.HTTP_201_CREATED)


class CVBuilderDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request, pk):
        try:
            job = CVBuilderJob.objects.get(pk=pk, user=request.user)
        except CVBuilderJob.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'id': job.pk, 'template': job.template, 'form_data': job.form_data, 'updated_at': job.updated_at})

    def patch(self, request, pk):
        try:
            job = CVBuilderJob.objects.get(pk=pk, user=request.user)
        except CVBuilderJob.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if 'template' in request.data:
            TEMPLATE_MIN_PLAN = {
                'classic': 'free', 'minimal': 'free',
                'modern': 'starter', 'creative': 'starter', 'developer': 'starter',
                'custom': 'pro',
            }
            PLAN_ORDER = ['free', 'starter', 'pro']
            subscription = getattr(request.user, 'subscription', None)
            user_plan = subscription.plan.name if subscription else 'free'
            new_template = request.data['template']
            required = TEMPLATE_MIN_PLAN.get(new_template, 'starter')
            if PLAN_ORDER.index(user_plan) < PLAN_ORDER.index(required):
                return Response(
                    {'error': f'The {new_template} template requires the {required.title()} plan or above.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            job.template = new_template

        if 'form_data' in request.data:
            job.form_data = request.data['form_data']
        job.save()
        return Response({'id': job.pk, 'template': job.template, 'updated_at': job.updated_at})

    def delete(self, request, pk):
        try:
            job = CVBuilderJob.objects.get(pk=pk, user=request.user)
        except CVBuilderJob.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── ATS Analyzer ────────────────────────────────────────────────────────────


class ATSAnalyzerView(APIView):
    parser_classes = [MultiPartParser, JSONParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = getattr(request.user, 'subscription', None)

        can_analyze, reason = subscription.can_analyze_ats() if subscription else (False, 'No active plan found.')
        if not can_analyze:
            return Response({'error': reason}, status=status.HTTP_403_FORBIDDEN)

        cv_file = request.data.get('cv_file')
        job_description = request.data.get('job_description', '').strip()

        if not cv_file:
            return Response({'error': 'cv_file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not job_description:
            return Response({'error': 'job_description is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cv_bytes = cv_file.read()
            cv_text = extract_text(cv_bytes, cv_file.name)
            if not cv_text:
                return Response({'error': 'Could not extract text from the CV file.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("ATS extract error: %s", e)
            return Response({'error': 'Failed to read CV file.'}, status=status.HTTP_400_BAD_REQUEST)

        if django_settings.AI_PROVIDER == 'claude':
            from .services.claude_service import analyze_ats as claude_ats
            result = claude_ats(cv_text, job_description)
        else:
            from .services.gemini_service import analyze_ats
            result = analyze_ats(cv_text, job_description)

        subscription.increment_ats()

        plan_name = subscription.plan.name
        if plan_name == 'free':
            result['suggestions'] = []

        ats_limit = subscription.plan.ats_limit
        result['ats_count'] = subscription.ats_count
        result['ats_limit'] = ats_limit if ats_limit != -1 else 'unlimited'

        return Response(result)
