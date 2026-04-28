from django.db import models


class CVUpload(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

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
