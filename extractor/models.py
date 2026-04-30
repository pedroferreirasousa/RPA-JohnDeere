from django.db import models


class StageChassi(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendente'),
        (STATUS_PROCESSING, 'Processando'),
        (STATUS_DONE, 'Concluído'),
        (STATUS_ERROR, 'Erro'),
    ]

    pin = models.CharField(max_length=50, unique=True)
    source = models.CharField(max_length=100, default='api')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    added_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_msg = models.TextField(blank=True)

    class Meta:
        ordering = ['-added_at']
        verbose_name = 'Chassi em Stage'
        verbose_name_plural = 'Chassis em Stage'

    def __str__(self):
        return f"{self.pin} ({self.get_status_display()})"


class RunLog(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    total_chassis = models.IntegerField(default=0)
    inserted = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    detail = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Log de Execução'
        verbose_name_plural = 'Logs de Execução'

    def __str__(self):
        return f"Run {self.started_at:%d/%m/%Y %H:%M} — {self.total_chassis} chassis"


class AuthToken(models.Model):
    token = models.TextField()
    captured_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-captured_at']
        verbose_name = 'Token JD'
        verbose_name_plural = 'Tokens JD'

    def __str__(self):
        return f"Token {self.captured_at:%d/%m/%Y %H:%M} ({'ativo' if self.is_active else 'expirado'})"
