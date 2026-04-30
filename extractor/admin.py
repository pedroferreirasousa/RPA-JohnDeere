from django.contrib import admin
from .models import StageChassi, RunLog, AuthToken


@admin.register(StageChassi)
class StageChassiAdmin(admin.ModelAdmin):
    list_display = ['pin', 'status', 'source', 'added_at', 'processed_at']
    list_filter = ['status', 'source']
    search_fields = ['pin']
    readonly_fields = ['added_at', 'processed_at']


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ['started_at', 'finished_at', 'total_chassis', 'inserted', 'errors']
    readonly_fields = ['started_at', 'finished_at', 'total_chassis', 'inserted', 'errors', 'detail']


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ['captured_at', 'is_active']
    readonly_fields = ['token', 'captured_at']
