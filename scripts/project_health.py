#!/usr/bin/env python3
from pathlib import Path
import base64
import json
import re
import sys

ROOT = Path.cwd()
warnings = []
failures = []

def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

frontend = ROOT / "frontend"
workflows = ROOT / ".github" / "workflows"

if not frontend.exists():
    failures.append("Brak katalogu frontend/")

js_files = list(frontend.glob("*.js")) if frontend.exists() else []
css_files = list(frontend.glob("*.css")) if frontend.exists() else []

if len(js_files) > 20:
    warnings.append(
        f"Frontend ma {len(js_files)} osobnych plików JS — warto dalej konsolidować moduły."
    )

if len(css_files) > 20:
    warnings.append(
        f"Frontend ma {len(css_files)} osobnych plików CSS — warto dalej konsolidować style."
    )

def b64url_decode(s):
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode()).decode("utf-8", errors="ignore")

def jwt_is_service_role(token):
    parts = token.split(".")
    if len(parts) != 3:
        return False
    try:
        payload = json.loads(b64url_decode(parts[1]))
        return payload.get("role") == "service_role"
    except Exception:
        return False

assignment_rx = re.compile(
    r"(?:SUPABASE_SERVICE_ROLE_KEY|SERVICE_ROLE_KEY)\s*[:=]\s*[\"']([^\"']{20,})[\"']",
    re.I,
)
secret_key_rx = re.compile(r"\bsb_secret_[A-Za-z0-9_-]{20,}\b")
jwt_rx = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")

if frontend.exists():
    for p in frontend.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in {".js", ".html", ".json", ".css"}:
            continue
        txt = read(p)

        if secret_key_rx.search(txt):
            failures.append(f"Rzeczywisty Supabase secret key w frontendzie: {p}")

        if assignment_rx.search(txt):
            failures.append(f"Service-role key przypisany w frontendzie: {p}")

        for token in jwt_rx.findall(txt):
            if jwt_is_service_role(token):
                failures.append(f"JWT z role=service_role w frontendzie: {p}")
                break

index = read(frontend / "index.html")
if "@supabase/supabase-js@2.112.3" not in index:
    warnings.append("Supabase JS nie jest przypięty do 2.112.3.")

if "app-meta.js?v=" not in index:
    warnings.append("Brak centralnego app-meta.js z cache-bust w index.html.")

sw = read(frontend / "sw.js")
if "cache.addAll(ASSETS)" in sw:
    failures.append("Service worker nadal używa kruchego cache.addAll(ASSETS).")

if "tenis-ai-v78e" not in sw:
    warnings.append("Service worker nie ma wersjonowanego cache Tenis AI.")

if "readability-v753.js" in index:
    warnings.append("readability-v753.js nadal jest ładowany mimo że ui-v751 ma własne match totals.")

restore = read(frontend / "restore-v762.js")
if "setInterval(refresh,1200)" in restore:
    failures.append("Stary polling UI co 1.2 s nadal istnieje.")

if workflows.exists():
    for wf in list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml")):
        txt = read(wf)
        low = txt.lower()

        if "git push" not in low:
            continue

        if "git fetch origin" not in low or "git rebase origin/main" not in low:
            warnings.append(
                f"{wf}: workflow pushuje do repo bez fetch/rebase safeguard."
            )

        if "concurrency:" not in low:
            warnings.append(
                f"{wf}: workflow pushujący do repo nie ma concurrency guard."
            )

print("=== Tenis AI v7.8E11.4 Project Health ===")
print(f"JS files:  {len(js_files)}")
print(f"CSS files: {len(css_files)}")

for w in warnings:
    print("WARN:", w)

for f in failures:
    print("FAIL:", f)

print(f"\nSummary: {len(failures)} FAIL / {len(warnings)} WARN")

if failures:
    sys.exit(1)

print("Project health: PASS")
