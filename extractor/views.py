import json
import threading
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import AuthToken, RunLog, StageChassi

# ── In-memory job tracker (single-admin portal) ───────────────────────────────
# Armazena status dos jobs em memória (auth e implement rodam em background)
_jobs: dict = {}


# ── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard(request):
    active_token = AuthToken.objects.filter(is_active=True).order_by('-captured_at').first()
    pending_chassis = StageChassi.objects.filter(status=StageChassi.STATUS_PENDING).order_by('-added_at')
    run_logs = RunLog.objects.all()[:20]
    done_count = StageChassi.objects.filter(status=StageChassi.STATUS_DONE).count()

    return render(request, 'extractor/dashboard.html', {
        'active_token': active_token,
        'pending_chassis': pending_chassis,
        'pending_count': pending_chassis.count(),
        'run_logs': run_logs,
        'done_count': done_count,
    })


# ── Auth ──────────────────────────────────────────────────────────────────────

@require_http_methods(["POST"])
def auth_start(request):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "running",
        "message": "Iniciando navegador interativo...",
        "vnc_url": None,
    }
    t = threading.Thread(target=_run_auth, args=(job_id,), daemon=True)
    t.start()
    return JsonResponse({"job_id": job_id})


def _run_auth(job_id):
    import django.db
    django.db.close_old_connections()

    try:
        from rpa.auth_capture import iniciar_vnc, parar_vnc, capturar_token_interativo

        _jobs[job_id]["message"] = "Iniciando tela virtual e navegador..."
        iniciar_vnc()

        _jobs[job_id]["message"] = "Navegador aberto — aguarde o carregamento e aprove o MFA no celular."
        _jobs[job_id]["vnc_url"] = "http://localhost:6080/vnc.html?autoconnect=true&resize=scale"

        token = capturar_token_interativo()

        django.db.close_old_connections()
        AuthToken.objects.filter(is_active=True).update(is_active=False)
        AuthToken.objects.create(token=token)

        _jobs[job_id] = {"status": "done", "message": "Token capturado com sucesso!", "vnc_url": None}

    except Exception as e:
        _jobs[job_id] = {"status": "error", "message": f"Erro: {e}", "vnc_url": None}

    finally:
        try:
            from rpa.auth_capture import parar_vnc
            parar_vnc()
        except Exception:
            pass


def auth_status(request, job_id):
    job = _jobs.get(job_id, {"status": "not_found", "message": "Job não encontrado"})
    return JsonResponse(job)


@require_http_methods(["POST"])
def auth_manual_save(request):
    """Salva um Bearer token colado manualmente pelo usuário."""
    try:
        data = json.loads(request.body)
        token = data.get("token", "").strip()
    except (json.JSONDecodeError, AttributeError):
        token = request.POST.get("token", "").strip()

    if not token:
        return JsonResponse({"error": "Token vazio."}, status=400)

    if not token.startswith("Bearer "):
        token = f"Bearer {token}"

    AuthToken.objects.filter(is_active=True).update(is_active=False)
    AuthToken.objects.create(token=token)

    return JsonResponse({"status": "ok", "message": "Token salvo com sucesso!"})


# ── Implement ─────────────────────────────────────────────────────────────────

@require_http_methods(["POST"])
def implement_start(request):
    active_token = AuthToken.objects.filter(is_active=True).order_by('-captured_at').first()
    if not active_token:
        return JsonResponse({"error": "Nenhum token ativo. Autentique primeiro."}, status=400)

    pending_pins = list(
        StageChassi.objects.filter(status=StageChassi.STATUS_PENDING).values_list('pin', flat=True)
    )
    if not pending_pins:
        return JsonResponse({"error": "Nenhum chassi pendente."}, status=400)

    # Marca todos como "processando" para evitar duplo clique
    StageChassi.objects.filter(status=StageChassi.STATUS_PENDING).update(
        status=StageChassi.STATUS_PROCESSING
    )

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "running",
        "message": f"Iniciando processamento de {len(pending_pins)} chassis...",
        "total": len(pending_pins),
        "done": 0,
    }

    t = threading.Thread(
        target=_run_implement,
        args=(job_id, pending_pins, active_token.token),
        daemon=True,
    )
    t.start()

    return JsonResponse({"job_id": job_id, "total": len(pending_pins)})


def _run_implement(job_id, chassis_list, token):
    import django.db
    django.db.close_old_connections()

    run_log = RunLog.objects.create(total_chassis=len(chassis_list))
    inserted_total = 0
    errors_total = 0
    detail_lines = []

    try:
        from rpa.processor import processar_chassi

        for i, pin in enumerate(chassis_list, 1):
            _jobs[job_id]["message"] = f"[{i}/{len(chassis_list)}] Processando {pin}..."
            _jobs[job_id]["done"] = i - 1

            try:
                n = processar_chassi(pin, token)
                inserted_total += n
                detail_lines.append(f"OK {pin}: {n} linhas inseridas")
                StageChassi.objects.filter(pin=pin).update(
                    status=StageChassi.STATUS_DONE,
                    processed_at=timezone.now(),
                    error_msg='',
                )
            except Exception as e:
                errors_total += 1
                detail_lines.append(f"ERRO {pin}: {e}")
                StageChassi.objects.filter(pin=pin).update(
                    status=StageChassi.STATUS_ERROR,
                    error_msg=str(e)[:500],
                )

        django.db.close_old_connections()
        run_log.finished_at = timezone.now()
        run_log.inserted = inserted_total
        run_log.errors = errors_total
        run_log.detail = "\n".join(detail_lines)
        run_log.save()

        _jobs[job_id] = {
            "status": "done",
            "message": f"Concluído! {inserted_total} linhas inseridas, {errors_total} erros.",
            "inserted": inserted_total,
            "errors": errors_total,
            "total": len(chassis_list),
            "done": len(chassis_list),
        }

    except Exception as e:
        run_log.finished_at = timezone.now()
        run_log.errors = len(chassis_list)
        run_log.detail = f"Erro geral: {e}"
        run_log.save()
        _jobs[job_id] = {"status": "error", "message": f"Erro geral: {e}"}


def implement_status(request, job_id):
    job = _jobs.get(job_id, {"status": "not_found", "message": "Job não encontrado"})
    return JsonResponse(job)


# ── API: Ingest chassis (chamada pelo Airflow) ─────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def api_ingest_chassis(request):
    api_key = request.headers.get('X-Api-Key', '')
    if api_key != settings.PORTAL_API_KEY:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
        chassis_list = data.get('chassis', [])
        source = data.get('source', 'airflow')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "JSON inválido"}, status=400)

    if not isinstance(chassis_list, list):
        return JsonResponse({"error": "chassis deve ser uma lista"}, status=400)

    added = 0
    skipped = 0
    for pin in chassis_list:
        pin_clean = str(pin).strip()
        if not pin_clean:
            continue
        _, created = StageChassi.objects.get_or_create(
            pin=pin_clean,
            defaults={'source': source, 'status': StageChassi.STATUS_PENDING},
        )
        if created:
            added += 1
        else:
            skipped += 1

    return JsonResponse({"added": added, "skipped": skipped, "total": len(chassis_list)})
