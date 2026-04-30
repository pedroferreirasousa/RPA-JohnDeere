import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from extractor.models import StageChassi


class Command(BaseCommand):
    help = "Busca chassis da API externa e salva na fila de processamento (stage)"

    def handle(self, *args, **options):
        if not settings.CHASSIS_API_URL:
            self.stderr.write("CHASSIS_API_URL não configurada no .env")
            return

        headers = {}
        if settings.CHASSIS_API_KEY:
            headers["Authorization"] = f"Bearer {settings.CHASSIS_API_KEY}"

        try:
            resp = requests.get(settings.CHASSIS_API_URL, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            self.stderr.write(f"Erro ao chamar API externa: {e}")
            return

        data = resp.json()
        if isinstance(data, dict):
            chassis_list = data.get('chassis', data.get('pins', data.get('data', [])))
        else:
            chassis_list = data

        added = 0
        skipped = 0
        for pin in chassis_list:
            pin_clean = str(pin).strip()
            if not pin_clean:
                continue
            _, created = StageChassi.objects.get_or_create(
                pin=pin_clean,
                defaults={'source': 'api_external', 'status': StageChassi.STATUS_PENDING},
            )
            if created:
                added += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{added} chassis adicionados, {skipped} já existiam ({len(chassis_list)} retornados pela API)"
            )
        )
