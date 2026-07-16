from __future__ import annotations

import ast
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg", ".bmp", ".avif"}
FORBIDDEN_PARTS = {".git", ".venv", "__pycache__", "logs", "backups"}
FORBIDDEN_TEXT = {
    "bubblebot" + ".tdvr.tw",
    "lin200" + "60613",
    "lin" + "0613",
    "haJ4" + "EUufPk",
    "GENSHIN_EMBEDDED_" + "COMPLETION_67",
    "'id': '80" + "490'",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "discord_webhook": re.compile(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9._-]+"),
}

errors: list[str] = []
files = [path for path in ROOT.rglob("*") if path.is_file()]
for path in files:
    relative = path.relative_to(ROOT)
    if path.suffix.lower() in IMAGE_SUFFIXES:
        errors.append(f"image file: {relative}")
    if any(part in FORBIDDEN_PARTS for part in relative.parts):
        errors.append(f"private/runtime path: {relative}")
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
    try:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except SyntaxError as exc:
        errors.append(f"python syntax: {path.relative_to(ROOT)}:{exc.lineno}:{exc.msg}")

manifest_path = ROOT / "SOURCE_MANIFEST.sha256"
if not manifest_path.is_file():
    errors.append("missing SOURCE_MANIFEST.sha256")
else:
    listed: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"invalid hash manifest line: {line}")
            continue
        listed[relative] = digest
    expected = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(listed) != expected:
        errors.append(
            f"hash manifest file set mismatch: listed={len(listed)} expected={len(expected)}"
        )
    for relative, digest in listed.items():
        path = ROOT / relative
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(f"hash mismatch: {relative}")

site_text = "\n".join(
    path.read_text(encoding="utf-8-sig", errors="replace")
    for path in (ROOT / "site").rglob("*")
    if path.is_file()
)
if re.search(r"<img\b", site_text, flags=re.IGNORECASE):
    errors.append("site still contains an img element")
if re.search(r"(?:/assets/(?:games|social)/|favicon\.(?:png|ico|svg))", site_text, flags=re.IGNORECASE):
    errors.append("site still references removed image assets")

if errors:
    print("PUBLIC SOURCE CHECK FAILED")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)
print(f"PUBLIC SOURCE CHECK OK: {len(files)} files")
