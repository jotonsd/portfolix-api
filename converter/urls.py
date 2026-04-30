from django.urls import path
from .views import ConvertCVView, CVDetailView, CVPreviewView, JobStatusView, PublicPortfolioView

urlpatterns = [
    path('convert/', ConvertCVView.as_view(), name='convert-cv'),
    path('convert/<int:pk>/', CVDetailView.as_view(), name='cv-detail'),
    path('convert/<int:pk>/preview/', CVPreviewView.as_view(), name='cv-preview'),
    path('jobs/', JobStatusView.as_view(), name='job-status'),
    path('portfolio/<uuid:token>/', PublicPortfolioView.as_view(), name='public-portfolio'),
]
