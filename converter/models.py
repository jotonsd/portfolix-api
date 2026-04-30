import uuid
from django.conf import settings
from django.db import models


class CVUpload(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cv_uploads', null=True, blank=True)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    cv_file = models.FileField(upload_to='cvs/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    generated_html = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"CV #{self.pk} — {self.status}"
