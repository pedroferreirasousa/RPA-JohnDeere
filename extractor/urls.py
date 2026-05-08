from django.urls import path
from . import views

urlpatterns = [
    # Portal home
    path('', views.home, name='home'),

    # JD OptionCode RPA
    path('rpa/jd-optionscode/',                                     views.dashboard,              name='jd_optionscode_dashboard'),
    path('rpa/jd-optionscode/auth/start/',                          views.auth_start,             name='auth_start'),
    path('rpa/jd-optionscode/auth/status/<str:job_id>/',            views.auth_status,            name='auth_status'),
    path('rpa/jd-optionscode/auth/manual-save/',                    views.auth_manual_save,       name='auth_manual_save'),
    path('rpa/jd-optionscode/implement/start/',                     views.implement_start,        name='implement_start'),
    path('rpa/jd-optionscode/implement/status/<str:job_id>/',       views.implement_status,       name='implement_status'),
    path('rpa/jd-optionscode/chassis/upload-excel/',                views.upload_chassis_excel,   name='upload_chassis_excel'),

    # API interna (usada pelo Airflow — mantida na raiz)
    path('api/ingest/', views.api_ingest_chassis, name='api_ingest'),
]
