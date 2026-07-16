#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_NAME = "Milora_tool"
LICENSE_ID = "GPL-3.0-only"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg", ".bmp", ".avif"}
SITE_SUFFIXES = {".html", ".css", ".js", ".json", ".xml", ".txt", ".config"}
ROOT_FILES = {
    ".achievement-hub-root",
    ".gitignore",
    "requirements.txt",
    "啟動後端.cmd",
    "關閉後端.cmd",
    "重啟後端.cmd",
    "檢查後端.cmd",
    "verify_installation.cmd",
}
SCRIPT_FILES = {
    "scripts/start_backend.ps1",
    "scripts/stop_backend.ps1",
    "scripts/restart_backend.ps1",
    "scripts/check_backend.ps1",
    "scripts/verify_installation.ps1",
    "scripts/run_backend_host.py",
    "scripts/setup/01_install_iis.ps1",
    "scripts/setup/02_install_backend.ps1",
    "scripts/setup/03_configure_iis_site.ps1",
    "scripts/setup/05_configure_https.ps1",
    "scripts/maintenance/backup_database.ps1",
    "scripts/maintenance/register_daily_backup.ps1",
    "scripts/maintenance/remove_startup.ps1",
    "scripts/maintenance/test_email.ps1",
    "tools/maintenance/add_game.py",
    "tools/maintenance/create_safety_backup.py",
    "tools/maintenance/build_open_source.py",
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def is_within(path: Path, parent: Path) -> bool:
    resolved = path.resolve()
    base = parent.resolve()
    return resolved == base or base in resolved.parents


def safe_remove_tree(path: Path, parent: Path, expected_prefix: str) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    if not is_within(resolved, parent) or not resolved.name.startswith(expected_prefix):
        fail(f"Refusing to remove unsafe path: {resolved}")
    shutil.rmtree(resolved)


def read_text(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8-sig")


def write_text(root: Path, relative: str, value: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def copy_file(source_root: Path, target_root: Path, relative: str) -> None:
    source = source_root / relative
    if not source.is_file():
        fail(f"Missing source file: {source}")
    target = target_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_source(source_root: Path, target_root: Path) -> None:
    for path in sorted((source_root / "backend").rglob("*.py")):
        if "__pycache__" not in path.parts:
            copy_file(source_root, target_root, path.relative_to(source_root).as_posix())
    for path in sorted((source_root / "site").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SITE_SUFFIXES:
            continue
        if re.fullmatch(r"google[a-z0-9]+\.html", path.name, flags=re.IGNORECASE):
            continue
        copy_file(source_root, target_root, path.relative_to(source_root).as_posix())
    for relative in sorted(ROOT_FILES | SCRIPT_FILES):
        copy_file(source_root, target_root, relative)


def patch_registry(root: Path) -> None:
    path = root / "site/game-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    for project in manifest.get("projects", []):
        if isinstance(project, dict):
            project["iconEndpoint"] = ""
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    registry = read_text(root, "backend/core/game_registry.py")
    registry, count = re.subn(
        r'("iconEndpoint"\s*:\s*)"/assets/games/[^"\r\n]+"',
        r'\1""',
        registry,
    )
    if count < 5:
        fail("Default game icon endpoints were not removed")
    write_text(root, "backend/core/game_registry.py", registry)


def patch_site(root: Path) -> None:
    domains = (
        "http://bubblebot" + ".tdvr.tw:817",
        "https://bubblebot" + ".tdvr.tw:817",
        "http://bubblebot" + ".tdvr.tw",
        "https://bubblebot" + ".tdvr.tw",
    )
    image_path = re.compile(
        r"/assets/(?:games|social)/[^\s\"'`)<>]+\.(?:png|jpe?g|webp|gif|ico|svg|bmp|avif)(?:\?[^\s\"'`)<>]*)?",
        flags=re.IGNORECASE,
    )
    for path in sorted((root / "site").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SITE_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8-sig")
        for domain in domains:
            text = text.replace(domain, "http://127.0.0.1:8000")
        text = re.sub(
            r"<link\b[^>]*(?:rel=[\"'][^\"']*(?:icon|apple-touch-icon)[^\"']*[\"']|href=[\"'][^\"']*favicon[^\"']*[\"'])[^>]*>\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r'<div\s+class=["\']socialLinks\s+(?:sidebarSocialLinks|mobileHomeSocialLinks)["\'][^>]*>.*?</div>',
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(r"<img\b[^>]*>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = image_path.sub("", text)
        relative = path.relative_to(root).as_posix()
        if relative == "site/index.html":
            text = text.replace(
                "mobileCurrentIcon.hidden=!project?.iconEndpoint;if(project?.iconEndpoint)mobileCurrentIcon.src=project.iconEndpoint+'?hub=mobile-top';",
                "if(mobileCurrentIcon){mobileCurrentIcon.hidden=true;mobileCurrentIcon.removeAttribute('src')}",
            )
            text = text.replace("mobileHomeSocialLinks.hidden=currentPage!=='home';", "")
        elif relative == "site/assets/shared/game-app.js":
            text = text.replace("$('icon').src=state.config.iconEndpoint;", "")
        elif relative == "site/_projects/redeem/index.html":
            text = re.sub(
                r"function gameIcon\(gameId\)\{return `[^`]*`\}",
                'function gameIcon(gameId){return ""}',
                text,
                count=1,
            )
        path.write_text(text, encoding="utf-8")


def patch_empty_data_mode(root: Path) -> None:
    relative = "backend/main.py"
    text = read_text(root, relative)
    anchor = 'APP_ENV = os.getenv("APP_ENV", "development").lower()\n'
    if anchor not in text:
        fail("APP_ENV anchor not found")
    text = text.replace(
        anchor,
        anchor + 'OPEN_SOURCE_EMPTY_DATA = os.getenv("OPEN_SOURCE_EMPTY_DATA", "1").lower() in {"1","true","yes","on"}\n',
        1,
    )
    start = text.index("        migration_stamp=now()\n", text.index("def init_db()"))
    end_marker = (
        '        db.execute(\n'
        '            "insert or ignore into schema_migrations(name,applied_at,details_json) values(?,?,?)",\n'
        '            (\n'
        '                "2026-06-26-governance-control-v1",'
    )
    end = text.index(end_marker, start)
    replacement = '''        migration_stamp=now()
        if not OPEN_SOURCE_EMPTY_DATA:
            existing_wuwa_catalog_count = int(
                db.execute("select count(*) from game_catalog_items where game_id='wuwa'").fetchone()[0]
            )
            if existing_wuwa_catalog_count:
                migrate_wuwa_to_official_ids(db,migration_stamp)
            for project in enabled_projects():
                game_id=str(project.get("id") or "").strip()
                if game_id:
                    _sync_registered_catalog(db,game_id)
                    _sync_achievement_categories(db,game_id)
            migrate_wuwa_to_official_ids(db,migration_stamp)
            _bootstrap_achievement_identities(db)

        for project in enabled_projects():
            game_id=str(project.get("id") or "").strip()
            if game_id:
                if not OPEN_SOURCE_EMPTY_DATA:
                    _sync_registered_relations(db,game_id)
                for field_name in sorted(DERIVED_RELATION_FIELDS):
                    db.execute(
                        """insert into achievement_field_registry(
                        game_id,field_name,classification,mapped_field,active,created_by,created_at,updated_at)
                        values(?,?, 'system_derived_relation','',1,null,?,?)
                        on conflict(game_id,field_name) do update set
                        classification='system_derived_relation',mapped_field='',active=1,updated_at=excluded.updated_at""",
                        (game_id,field_name,migration_stamp,migration_stamp),
                    )
        _migrate_orphan_identity_cleanup(db)
        _migrate_wuwa_shared_model(db)
        if not OPEN_SOURCE_EMPTY_DATA:
            _verify_wuwa_shared_model(db)
            _repair_hsr_catalog_rewards(db)
            normalize_all_game_official_order(db,migration_stamp)
            _verify_wuwa_shared_model(db)
            verify_official_id_model(db)
'''
    text = text[:start] + replacement + text[end:]

    static_anchor = "def _html_no_store_response(index_file: Path):\n"
    if static_anchor not in text:
        fail("Static response anchor not found")
    static_routes = '''@app.get("/game-manifest.json")
def public_game_manifest():
    manifest = SITE_DIR / "game-manifest.json"
    if not manifest.is_file():
        raise HTTPException(status_code=404, detail="game manifest not found")
    return FileResponse(manifest, media_type="application/json", headers={"Cache-Control": "no-store"})


@app.get("/assets/{asset_path:path}")
def public_site_asset(asset_path: str):
    assets_root = (SITE_DIR / "assets").resolve()
    candidate = (assets_root / asset_path).resolve()
    if assets_root not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(candidate)


@app.get("/robots.txt")
def public_robots():
    path = SITE_DIR / "robots.txt"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="robots.txt not found")
    return FileResponse(path, media_type="text/plain")


@app.get("/sitemap.xml")
def public_sitemap():
    path = SITE_DIR / "sitemap.xml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="sitemap.xml not found")
    return FileResponse(path, media_type="application/xml")


'''
    text = text.replace(static_anchor, static_routes + static_anchor, 1)
    write_text(root, relative, text)


def strip_embedded_data(root: Path) -> None:
    relative = "backend/services/game_data_sources.py"
    text = read_text(root, relative)
    embedded_name = "GENSHIN_EMBEDDED_" + "COMPLETION_67"
    text, count = re.subn(
        rf"{embedded_name}:\s*tuple\[dict\[str, Any\], \.\.\.\]\s*=\s*\(.*?\n\)\n\n\nclass RepositorySourceError",
        "GENSHIN_EMBEDDED_COMPLETION: tuple[dict[str, Any], ...] = ()\n\n\nclass RepositorySourceError",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        fail("Embedded achievement data block was not removed")
    text = text.replace(
        'GENSHIN_BUNDLED_COMPLETION_FILENAME = "bundled-completion-6.7.json"',
        'GENSHIN_BUNDLED_COMPLETION_FILENAME = "bundled-completion.json"',
    )
    text = re.sub(
        r'def load_bundled_genshin_completion_catalog\(data_dir: Path\) -> tuple\[list\[dict\[str, Any\]\], dict\[str, Any\]\]:\n\s+""".*?"""',
        'def load_bundled_genshin_completion_catalog(data_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:\n    """Load an operator-supplied completion catalog; no game records are bundled."""',
        text,
        count=1,
        flags=re.DOTALL,
    )
    text, count = re.subn(
        r"    embedded_used = payload is None\n    if payload is None:\n.*?        selected_path = \"embedded://genshin/6\.7\"\n",
        '''    embedded_used = False
    if payload is None:
        raise RepositorySourceError(
            "純程式碼公開版未附帶補全目錄；請由管理員提供具有使用權的資料檔。",
            code="bundled_completion_not_supplied",
            diagnostics={"searched_paths": [str(path) for path in candidate_paths], "load_error": load_error},
        )
''',
        text,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        fail("Embedded completion fallback was not removed")
    text = re.sub(
        r"    if len\(rows\) != 38:\n        raise RepositorySourceError\(.*?\n        \)\n",
        '''    if not rows:
        raise RepositorySourceError(
            "管理員提供的補全目錄沒有可用資料。",
            code="bundled_completion_empty",
            diagnostics={"path": selected_path},
        )
''',
        text,
        count=1,
        flags=re.DOTALL,
    )
    if "'id': '804" + "90'" in text or embedded_name in text:
        fail("Embedded achievement records remain")
    write_text(root, relative, text)


def patch_start_script(root: Path) -> None:
    relative = "scripts/start_backend.ps1"
    text = read_text(root, relative)
    start = text.find("    $RepairMarker = Join-Path $Root")
    end = text.find("    $Python = Join-Path $Root '.venv\\Scripts\\python.exe'", start)
    if start < 0 or end < 0:
        fail("Private startup repair block was not found")
    write_text(root, relative, text[:start] + text[end:])


def public_documents(root: Path, version: str, release_id: str) -> None:
    env_example = """APP_ENV=development
PUBLIC_BASE_URL=http://127.0.0.1:8000
TRUSTED_HOSTS=localhost,127.0.0.1
TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
SESSION_COOKIE_SECURE=false
SESSION_SECONDS=2592000
VERIFY_TOKEN_SECONDS=86400
RESET_TOKEN_SECONDS=1800
DATABASE_PATH=data/app.db
OPEN_SOURCE_EMPTY_DATA=1
SITE_OWNER_EMAIL=owner@example.com
ADMIN_EMAILS=admin@example.com
MAIL_DELIVERY=console
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=noreply@example.com
SMTP_STARTTLS=true
SMTP_SSL=false
SMTP_VALIDATE_CERT=true
"""
    write_text(root, ".env.example", env_example)
    write_text(
        root,
        ".gitignore",
        """.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
data/
logs/
backups/
site/assets/games/
site/assets/social/
site/favicon.*
.vscode/
.idea/
.DS_Store
Thumbs.db
""",
    )
    write_text(
        root,
        "README.md",
        f"""# Milora_tool

遊戲成就紀錄器的 GPL-3.0 純程式碼公開版，版本 `{version}`。

此套件只包含應用程式原始碼，不包含遊戲圖片、專案代表圖、社群品牌圖示、正式成就目錄、關聯資料、來源快照、資料庫、帳號、郵件、日誌或備份。首次啟動會建立空白資料庫，成就列表預設為空白。

## Windows 啟用方式

```powershell
py -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\\啟動後端.cmd
```

開啟 `http://127.0.0.1:8000`。公開版後端會同時提供 API 與前端靜態檔，不需要先安裝 IIS。

`OPEN_SOURCE_EMPTY_DATA=1` 會略過正式遊戲目錄啟動門檻。若自行匯入或同步第三方資料，必須確認資料來源授權及使用條款。

## 授權

本套件內由專案作者擁有權利的程式碼依 GNU General Public License v3.0 授權，完整條款見 `LICENSE`。外部依賴、遊戲名稱與商標仍適用各權利人的條款。
""",
    )
    write_text(
        root,
        "OPEN_SOURCE_SCOPE.md",
        """# 純程式碼公開範圍

## 已包含

- FastAPI 後端、SQLite 結構與 API 原始碼。
- 桌面版與手機版 HTML、CSS、JavaScript。
- 啟動、停止、重啟、安裝與一般維護腳本。
- 空白資料模式、開源同步工具及公開版檢查工具。

## 明確排除

- 所有 PNG、JPG、JPEG、WebP、GIF、ICO、SVG、BMP、AVIF 圖片。
- favicon、專案代表圖、遊戲圖示與社群品牌圖示。
- 正式成就名稱、條件、獎勵、版本、官方 ID 清單與內嵌補全記錄。
- 正式目錄、關聯資料、來源快照、SQLite、帳號、工作階段、操作紀錄、郵件、日誌、備份與 `.env`。
- 正式站台網域驗證檔、私人發布文件與私有環境設定。

公開版預設 `OPEN_SOURCE_EMPTY_DATA=1`，只略過需要正式遊戲資料的同步與驗證；一般資料表與管理功能仍會初始化。
""",
    )
    write_text(
        root,
        "THIRD_PARTY_NOTICES.md",
        """# 第三方與商標說明

本公開套件不綑綁 Python 虛擬環境或第三方遊戲資料。`requirements.txt` 的依賴由使用者另外安裝，並各自適用其上游授權條款。

來源同步程式可能連線至程式碼中設定的第三方儲存庫或網站。GPL-3.0 只涵蓋本套件中專案作者有權授權的程式碼，不改變外部網站、遊戲資料、名稱、圖像或商標的權利狀態。本專案與相關遊戲發行商或資料來源沒有從屬或官方認可關係。
""",
    )
    write_text(
        root,
        "SECURITY.md",
        """# 安全設定

- 不要提交 `.env`、資料庫、日誌、備份或 SMTP 密碼。
- 正式環境請使用 HTTPS、`APP_ENV=production` 與安全 Cookie。
- 請替換 `.env.example` 的範例站長信箱。
- 匯入外部資料前先在隔離環境檢查內容及來源。
""",
    )
    public_release = {
        "project_name": PROJECT_NAME,
        "version": version,
        "release_id": release_id,
        "channel": "source",
        "license": LICENSE_ID,
        "private_release": False,
        "public_release_safe": True,
        "source_only": True,
        "images_included": False,
        "game_data_included": False,
        "runtime_data_included": False,
    }
    write_text(root, "release-info.json", json.dumps(public_release, ensure_ascii=False, indent=2))


def download_license(root: Path) -> None:
    request = urllib.request.Request(
        "https://www.gnu.org/licenses/gpl-3.0.txt",
        headers={"User-Agent": "Milora_tool source release builder"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8")
    if "GNU GENERAL PUBLIC LICENSE" not in text or "Version 3, 29 June 2007" not in text:
        fail("Official GPL-3.0 text validation failed")
    write_text(root, "LICENSE", text)


def write_validator(root: Path) -> None:
    validator = r'''from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg", ".bmp", ".avif"}
FORBIDDEN_TEXT = {
    "bubblebot" + ".tdvr.tw",
    "lin200" + "60613",
    "haJ4" + "EUufPk",
    "GENSHIN_EMBEDDED_" + "COMPLETION_67",
    "'id': '804" + "90'",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}

errors: list[str] = []
files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]
for path in files:
    relative = path.relative_to(ROOT)
    if path.suffix.lower() in IMAGE_SUFFIXES:
        errors.append(f"image file: {relative}")
    if any(part in {".venv", "__pycache__", "logs", "backups", "data"} for part in relative.parts):
        errors.append(f"runtime path: {relative}")
    if path.name == ".env" or path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".pdf"}:
        errors.append(f"private/binary file: {relative}")
    if re.fullmatch(r"google[a-z0-9]+\.html", path.name, flags=re.IGNORECASE):
        errors.append(f"site verification file: {relative}")
    if path.suffix.lower() in {".py", ".html", ".css", ".js", ".json", ".xml", ".txt", ".md", ".ps1", ".cmd", ".config", ".example"} or path.name in {"LICENSE", ".gitignore"}:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for token in FORBIDDEN_TEXT:
            if token.casefold() in text.casefold():
                errors.append(f"forbidden text {token!r}: {relative}")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible {name}: {relative}")

for path in ROOT.rglob("*.py"):
    if ".git" in path.parts:
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except SyntaxError as exc:
        errors.append(f"python syntax: {path.relative_to(ROOT)}:{exc.lineno}:{exc.msg}")

site_text = "\n".join(path.read_text(encoding="utf-8-sig", errors="replace") for path in (ROOT / "site").rglob("*") if path.is_file())
if re.search(r"<img\b", site_text, flags=re.IGNORECASE):
    errors.append("site still contains an img element")
if re.search(r"(?:/assets/(?:games|social)/|favicon\.(?:png|ico|svg))", site_text, flags=re.IGNORECASE):
    errors.append("site still references removed image assets")

manifest = ROOT / "SOURCE_MANIFEST.sha256"
if manifest.is_file():
    listed: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"invalid hash manifest line: {line}")
            continue
        listed[relative] = digest
    expected = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file() and path != manifest and ".git" not in path.parts}
    if set(listed) != expected:
        errors.append(f"hash manifest file set mismatch: listed={len(listed)} expected={len(expected)}")
    for relative, digest in listed.items():
        path = ROOT / relative
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(f"hash mismatch: {relative}")

if errors:
    print("PUBLIC SOURCE CHECK FAILED")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)
print(f"PUBLIC SOURCE CHECK OK: {len(files)} files")
'''
    write_text(root, "tools/verify_public_source.py", validator)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_inventory_and_hashes(root: Path, version: str) -> dict[str, Any]:
    files = [path for path in sorted(root.rglob("*")) if path.is_file() and ".git" not in path.parts]
    payload = {
        "project_name": PROJECT_NAME,
        "version": version,
        "license": LICENSE_ID,
        "scope": "Files present before inventory and hash manifest generation",
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }
    write_text(root, "OPEN_SOURCE_INVENTORY.json", json.dumps(payload, ensure_ascii=False, indent=2))
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SOURCE_MANIFEST.sha256" or ".git" in path.parts:
            continue
        lines.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    write_text(root, "SOURCE_MANIFEST.sha256", "\n".join(lines))
    return payload


def validate(root: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(root / "tools/verify_public_source.py")],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if result.returncode:
        fail((result.stdout + "\n" + result.stderr).strip())
    print(result.stdout.strip())


def publish_stable(stage: Path, output: Path) -> None:
    parent = output.parent.resolve()
    previous = parent / f".{output.name}.previous"
    safe_remove_tree(previous, parent, f".{output.name}.previous")
    if output.exists():
        output.rename(previous)
    try:
        stage.rename(output)
        old_git = previous / ".git"
        if old_git.exists():
            old_git.rename(output / ".git")
        safe_remove_tree(previous, parent, f".{output.name}.previous")
    except Exception:
        if output.exists() and not previous.exists():
            safe_remove_tree(output, parent, output.name)
        if previous.exists() and not output.exists():
            previous.rename(output)
        raise


def zip_tree(source: Path, destination: Path, top_level: str) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and ".git" not in path.parts:
                archive.write(path, f"{top_level}/{path.relative_to(source).as_posix()}")


def build_release_copy(output: Path, release_root: Path, version: str, release_id: str) -> dict[str, Any]:
    version_root = release_root / version
    version_root.mkdir(parents=True, exist_ok=True)
    folder_name = f"{PROJECT_NAME}-{version}-GPL-3.0"
    package = version_root / folder_name
    zip_path = version_root / f"{folder_name}.zip"
    report_path = version_root / f"{folder_name}-build-report.json"
    safe_remove_tree(package, version_root, folder_name)
    if zip_path.exists():
        zip_path.unlink()
    shutil.copytree(output, package, ignore=shutil.ignore_patterns(".git"))
    validate(package)
    zip_tree(package, zip_path, folder_name)
    report = {
        "ok": True,
        "project_name": PROJECT_NAME,
        "version": version,
        "release_id": release_id,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_folder": str(output),
        "package": str(package),
        "zip": str(zip_path),
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256(zip_path),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def build(source_root: Path, output: Path, release_root: Path) -> dict[str, Any]:
    if output == source_root or is_within(output, source_root):
        fail("Open-source output must be outside the private project")
    release = json.loads((source_root / "release-info.json").read_text(encoding="utf-8-sig"))
    version = str(release.get("version") or "").strip()
    release_id = str(release.get("release_id") or "").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version) or not release_id:
        fail("Invalid release metadata")

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.parent / f".{output.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    safe_remove_tree(stage, output.parent, f".{output.name}.staging-")
    stage.mkdir(parents=True)
    try:
        copy_source(source_root, stage)
        patch_registry(stage)
        patch_site(stage)
        patch_empty_data_mode(stage)
        strip_embedded_data(stage)
        patch_start_script(stage)
        public_documents(stage, version, release_id)
        download_license(stage)
        write_validator(stage)
        inventory = write_inventory_and_hashes(stage, version)
        validate(stage)
        publish_stable(stage, output)
    finally:
        safe_remove_tree(stage, output.parent, f".{output.name}.staging-")

    report = build_release_copy(output, release_root, version, release_id)
    report["inventory_file_count"] = inventory["file_count"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Milora_tool GPL-3.0 pure source mirror.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output", default="")
    parser.add_argument("--release-root", default="")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve() if args.output else root.parent / f"{PROJECT_NAME}_OpenSource"
    release_root = Path(args.release_root).resolve() if args.release_root else root.parent / f"{PROJECT_NAME}_OpenSource_Releases"
    report = build(root, output.resolve(), release_root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Open-source build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
