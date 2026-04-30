from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('auth/start/', views.auth_start, name='auth_start'),
    path('auth/status/<str:job_id>/', views.auth_status, name='auth_status'),
    path('auth/manual-save/', views.auth_manual_save, name='auth_manual_save'),
    path('implement/start/', views.implement_start, name='implement_start'),
    path('implement/status/<str:job_id>/', views.implement_status, name='implement_status'),
    path('api/ingest/', views.api_ingest_chassis, name='api_ingest'),
]
