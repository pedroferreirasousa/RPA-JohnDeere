import os
import re
import subprocess
import threading
import time

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

JD_URL = "https://jdwarrantysystem.deere.com"

# ── VNC session management ────────────────────────────────────────────────────
_vnc_lock = threading.Lock()
_vnc_procs: list = []


def iniciar_vnc(display: str = ":99", vnc_port: int = 5900, ws_port: int = 6080) -> None:
    """Starts Xvfb + x11vnc + noVNC proxy so the browser is accessible via browser."""
    global _vnc_procs
    with _vnc_lock:
        parar_vnc()

        procs = []

        xvfb = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1280x900x24", "-ac"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(xvfb)
        time.sleep(1.2)

        vnc = subprocess.Popen(
            [
                "x11vnc",
                "-display", display,
                "-rfbport", str(vnc_port),
                "-nopw", "-forever", "-shared", "-quiet", "-noxdamage",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(vnc)
        time.sleep(0.8)

        novnc_bin = "/usr/share/novnc/utils/novnc_proxy"
        ws = subprocess.Popen(
            [novnc_bin, "--listen", str(ws_port), "--vnc", f"localhost:{vnc_port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(ws)
        time.sleep(0.5)

        _vnc_procs = procs


def parar_vnc() -> None:
    """Terminates all VNC-related processes."""
    global _vnc_procs
    for p in reversed(_vnc_procs):
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            pass
    _vnc_procs = []


def capturar_token_interativo(timeout_s: int = 300) -> str:
    """
    Abre Chromium headed no display virtual (:99) exposto via noVNC na porta 6080.
    Preenche usuário/senha automaticamente. O usuário só precisa aprovar o MFA
    no celular — o token Bearer é capturado automaticamente após o redirect.
    """
    os.environ["DISPLAY"] = ":99"
    token_ref = {"value": None}

    # ── Script injetado ANTES do SPA carregar ─────────────────────────────────
    # Intercepta fetch() e XMLHttpRequest para capturar o Bearer token assim que
    # o SPA o usar — independente de qual endpoint for chamado.
    _hook_script = """
        window.__capturedToken = null;

        // Hook fetch
        const _origFetch = window.fetch;
        window.fetch = function(...args) {
            try {
                const opts = args[1] || {};
                const headers = opts.headers || {};
                const auth = (typeof headers.get === 'function')
                    ? headers.get('authorization') || headers.get('Authorization')
                    : headers['authorization'] || headers['Authorization'] || '';
                if (auth && auth.startsWith('Bearer ') && !window.__capturedToken) {
                    window.__capturedToken = auth;
                }
            } catch(e) {}
            return _origFetch.apply(this, args);
        };

        // Hook XMLHttpRequest.setRequestHeader
        const _origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
        XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
            if (name && name.toLowerCase() === 'authorization' &&
                value && value.startsWith('Bearer ') && !window.__capturedToken) {
                window.__capturedToken = value;
            }
            return _origSetHeader.apply(this, arguments);
        };
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )

        # Injeta o hook antes de qualquer página carregar
        context.add_init_script(_hook_script)

        dt = os.getenv("JD_DEVICE_TOKEN", "")
        if dt:
            context.add_cookies([{
                "name": "DT",
                "value": dt,
                "domain": ".johndeere.com",
                "path": "/",
            }])

        page = context.new_page()

        # Captura via evento de request (backup para o hook JS)
        def capture_bearer(request):
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ") and not token_ref["value"]:
                token_ref["value"] = auth

        page.on("request", capture_bearer)

        # ── 1. Navega para o portal ──────────────────────────────────────────
        page.goto(JD_URL, wait_until="networkidle", timeout=30_000)

        # ── 2. Preenche username ─────────────────────────────────────────────
        try:
            page.wait_for_selector('input[name="identifier"]', timeout=20_000)
            page.fill('input[name="identifier"]', os.getenv("JD_USERNAME", ""))
            page.keyboard.press("Enter")
        except Exception:
            pass  # usuário pode preencher manualmente no VNC

        # ── 3. Seleciona Password e preenche senha ───────────────────────────
        try:
            page.wait_for_selector("text=Password", timeout=20_000)
            try:
                page.locator("li:has-text('Password')").get_by_role("button").first.click()
            except Exception:
                try:
                    page.locator("[data-se='okta-password']").click()
                except Exception:
                    page.get_by_text("Password", exact=True).locator("..").locator("button").click()

            page.wait_for_selector('input[type="password"]', timeout=15_000)
            page.fill('input[type="password"]', os.getenv("JD_PASSWORD", ""))
            page.keyboard.press("Enter")
        except Exception:
            pass  # usuário pode preencher manualmente no VNC

        # ── 4. Aguarda aprovação do MFA e URL do portal JD ──────────────────
        page.wait_for_url(
            re.compile(r"https://jdwarrantysystem\.deere\.com"),
            timeout=timeout_s * 1_000,
        )

        # Aguarda SPA terminar de montar e fazer chamadas iniciais
        page.wait_for_load_state("networkidle", timeout=30_000)
        page.wait_for_timeout(3_000)

        # ── 5. Verifica se o hook JS já capturou o token nas chamadas do SPA ─
        js_token = page.evaluate("() => window.__capturedToken || null")
        if js_token and not token_ref["value"]:
            token_ref["value"] = js_token

        # ── 6. Se ainda não tem token, tenta Okta localStorage ───────────────
        if not token_ref["value"]:
            try:
                ls_token = page.evaluate("""
                    () => {
                        try {
                            const raw = localStorage.getItem('okta-token-storage');
                            if (!raw) return null;
                            const obj = JSON.parse(raw);
                            const at = obj && (obj.accessToken || (obj['accessToken'] && obj['accessToken'].accessToken));
                            if (at && at.accessToken) return 'Bearer ' + at.accessToken;
                            if (typeof at === 'string') return 'Bearer ' + at;
                        } catch(e) {}
                        return null;
                    }
                """)
                if ls_token:
                    token_ref["value"] = ls_token
            except Exception:
                pass

        # ── 7. Se ainda não tem, aciona busca via UI para forçar chamada XHR ─
        if not token_ref["value"]:
            test_chassi = os.getenv("JD_TEST_CHASSI", "1NW4030MAM0210514")
            _capturar_token_via_busca(page, test_chassi, token_ref)
            # Confere novamente o hook JS após a busca
            if not token_ref["value"]:
                js_token = page.evaluate("() => window.__capturedToken || null")
                if js_token:
                    token_ref["value"] = js_token

        browser.close()

    if not token_ref["value"]:
        raise RuntimeError(
            "Token não capturado. Verifique se o login foi concluído e o portal carregou corretamente."
        )

    return token_ref["value"]


def _capturar_token_via_busca(page, chassi: str, token_ref: dict) -> None:
    """Digita o chassi no campo de busca do SPA e aciona a busca para disparar o XHR com Bearer token."""
    try:
        # Aguarda o campo de PIN aparecer
        search_input = page.wait_for_selector(
            'input[placeholder*="PIN"], input[placeholder*="pin"], input[placeholder*="minimum"]',
            timeout=15_000,
        )
        search_input.click()
        search_input.triple_click()
        search_input.fill(chassi)
        page.wait_for_timeout(500)

        # Estratégia 1: clica via JS no botão dentro do mesmo container do input
        clicked = page.evaluate("""
            (chassi) => {
                const input = document.querySelector(
                    'input[placeholder*="PIN"], input[placeholder*="pin"], input[placeholder*="minimum"]'
                );
                if (!input) return false;

                // Tenta o botão imediatamente após o input (irmão ou pai)
                const candidates = [
                    input.nextElementSibling,
                    input.parentElement && input.parentElement.querySelector('button'),
                    input.closest('form') && input.closest('form').querySelector('button'),
                    input.closest('[class*="search"]') && input.closest('[class*="search"]').querySelector('button'),
                    document.querySelector('button[type="submit"]'),
                    document.querySelector('.search-button'),
                    document.querySelector('[class*="search"] button'),
                ];
                for (const btn of candidates) {
                    if (btn && btn.tagName === 'BUTTON') {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }
        """, chassi)

        if not clicked:
            # Estratégia 2: Enter no campo
            search_input.press("Enter")

        # Aguarda a chamada XHR / fetch com o Bearer token
        page.wait_for_timeout(6_000)

    except Exception:
        pass


    """
    Faz login headless no JD Warranty System via Okta OIE.

    Fluxo:
      1. Navega para jdwarrantysystem.deere.com (redireciona para SSO Okta)
      2. Preenche username automaticamente
      3. Tela OIE: clica em "Select" ao lado de "Password"
      4. Preenche password automaticamente
      5. Okta envia push notification para o celular do admin
      6. Admin aprova no Okta Verify → página redireciona de volta ao portal JD
      7. Captura Bearer token via interceptação de request à /api/products

    Args:
        username: usuário JD
        password: senha JD
        timeout_push_s: segundos máximos aguardando aprovação do push (padrão: 5 min)

    Returns:
        Bearer token como string (ex: "Bearer eyJ...")

    Raises:
        RuntimeError: se o token não for capturado
    """
    token_ref = {"value": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        # Injeta DT cookie para ajudar no reconhecimento de dispositivo
        dt = os.getenv("JD_DEVICE_TOKEN", "")
        if dt:
            context.add_cookies([{
                "name": "DT",
                "value": dt,
                "domain": ".johndeere.com",
                "path": "/",
            }])

        page = context.new_page()

        # Intercepta qualquer request autenticada para capturar o Bearer token
        def capture_bearer(request):
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ") and not token_ref["value"]:
                token_ref["value"] = auth

        page.on("request", capture_bearer)

        # ── 1. Navega para o portal (redireciona para SSO) ──────────────────
        page.goto(JD_URL, wait_until="networkidle", timeout=30_000)

        # ── 2. Preenche username ─────────────────────────────────────────────
        page.wait_for_selector('input[name="identifier"]', timeout=20_000)
        page.fill('input[name="identifier"]', username)
        page.keyboard.press("Enter")

        # ── 3. OIE: seleciona método "Password" ─────────────────────────────
        # A tela "Verify it's you" aparece com uma lista de métodos de autenticação.
        # Precisamos clicar no botão "Select" ao lado de "Password".
        page.wait_for_selector("text=Password", timeout=20_000)

        try:
            # Estratégia 1: <li> contendo "Password" → botão dentro
            page.locator("li:has-text('Password')").get_by_role("button").first.click()
        except Exception:
            try:
                # Estratégia 2: atributo data-se do Okta OIE
                page.locator("[data-se='okta-password']").click()
            except Exception:
                # Estratégia 3: botão "Select" próximo ao texto Password
                page.get_by_text("Password", exact=True).locator("..").locator("button").click()

        # ── 4. Preenche password ─────────────────────────────────────────────
        page.wait_for_selector('input[type="password"]', timeout=15_000)
        page.fill('input[type="password"]', password)
        page.keyboard.press("Enter")

        # ── 5. Aguarda aprovação do push e redirect de volta ao portal JD ───
        # Após aprovar no Okta Verify, o Okta redireciona para jdwarrantysystem.deere.com
        page.wait_for_url(
            re.compile(r"https://jdwarrantysystem\.deere\.com"),
            timeout=timeout_push_s * 1_000,
        )

        # ── 6. Dispara request à API para capturar o Bearer token ────────────
        test_chassi = os.getenv("JD_TEST_CHASSI", "1NW4025MPKF190139")
        page.goto(
            f"{JD_URL}/api/products/{test_chassi}/options?export=EXCEL&language=EN",
            wait_until="networkidle",
            timeout=30_000,
        )
        page.wait_for_timeout(2_000)

        browser.close()

    if not token_ref["value"]:
        raise RuntimeError(
            "Token não capturado. Possíveis causas: login falhou, "
            "push não aprovado no tempo limite, ou a API /api/products não foi chamada."
        )

    return token_ref["value"]
