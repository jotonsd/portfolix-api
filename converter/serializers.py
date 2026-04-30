from rest_framework import serializers
from .models import CVUpload
from .services.claude_service import _strip_code_fences


class CVUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVUpload
        fields = ['id', 'share_token', 'cv_file', 'status', 'generated_html', 'error_message', 'created_at']
        read_only_fields = ['id', 'share_token', 'status', 'generated_html', 'error_message', 'created_at', 'user']

    def validate_cv_file(self, value):
        from .services.extractor import SUPPORTED_EXTENSIONS
        ext = value.name.rsplit('.', 1)[-1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            allowed = ', '.join(f'.{e}' for e in SUPPORTED_EXTENSIONS)
            raise serializers.ValidationError(
                f"Unsupported file type '.{ext}'. Allowed: {allowed}"
            )
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size must not exceed 10MB.")
        return value


class CVUploadResultSerializer(serializers.ModelSerializer):
    generated_html = serializers.SerializerMethodField()

    class Meta:
        model = CVUpload
        fields = ['id', 'share_token', 'status', 'generated_html', 'error_message', 'created_at']

    def get_generated_html(self, obj):
        return _strip_code_fences(obj.generated_html) if obj.generated_html else None
