"""Optional HSR translations using the existing parser and immutable source."""
from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping

LANGUAGES = {'en': 'EN', 'ja': 'JP', 'zh-Hans': 'CHS'}
PROJECT = 'Dimbreath/turnbasedgamedata'


def build_hsr_localizations(bundle: Any, parsed: Any,
                            languages: Mapping[str, Mapping[str, Any]], *, commit: str) -> dict:
    from backend.services.game_data_sources import parse_hsr_bundle
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Immutable commit required')
    ids = {str(row['achievement_id']) for row in parsed.rows}
    result: dict = {}
    coverage: dict = {}
    for language, maps in languages.items():
        if language not in LANGUAGES:
            continue
        localized = parse_hsr_bundle({**bundle.files, 'textmap': maps['textmap'],
                                      'textmap_main': maps.get('textmap_main', {})})
        if {str(row['achievement_id']) for row in localized.rows} != ids:
            raise ValueError('Localization changed achievement IDs')
        counts = dict.fromkeys(('name', 'condition', 'category'), 0)
        for row in localized.rows:
            values = {field: row[field] for field in counts if row.get(field)
                      and not (field == 'category' and row[field] == '未辨識分類')}
            if values:
                result.setdefault(str(row['achievement_id']), {})[language] = values
            for field in values:
                counts[field] += 1
        coverage[language] = counts
    return {'schema_version': 1, 'game_id': 'hsr', 'source_commit': commit,
            'items': result, 'coverage': coverage}


def fetch_hsr_localizations(bundle: Any, parsed: Any, *, timeout: int = 15,
                            request_json: Callable[[str], Any] | None = None) -> tuple[dict, list[str]]:
    from backend.services.game_data_sources import _request_bytes, _decode_json
    def request(url):
        if request_json:
            return request_json(url)
        raw, _ = _request_bytes(url, timeout=timeout, attempts=1, max_bytes=96 * 1024 * 1024)
        return _decode_json(raw, url=url)
    warnings = []
    try:
        if bundle.definition.game_id != 'hsr' or bundle.definition.repository_url != 'https://gitlab.com/' + PROJECT:
            raise ValueError('Unsupported HSR source')
        ref = urllib.parse.quote(str(bundle.source_ref), safe='')
        commit = str(request(f'https://gitlab.com/api/v4/projects/{urllib.parse.quote(PROJECT, safe="")}/repository/commits/{ref}').get('id') or '').lower()
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('Commit unavailable')
        base = f'https://gitlab.com/{PROJECT}/-/raw/{commit}/'
        # Verify every supplied file used for translated strings, including TextJoin.
        keys = ('achievements', 'groups', 'textmap', 'textmap_main', 'textjoin_config', 'textjoin_items')
        manifests = {m['key']: m for m in bundle.manifests}
        def verify(key):
            path = str(manifests.get(key, {}).get('path') or '')
            if not path.endswith('.json') or '..' in path or ':' in path or path.startswith('/'):
                raise ValueError('Unverified source path: ' + key)
            if request(base + path) != bundle.files[key]:
                raise ValueError('Source changed: ' + key)
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(verify, [key for key in keys if key in bundle.files]))
        def fetch_language(entry):
            language, suffix = entry
            try:
                maps = {'textmap': request(base + f'TextMap/TextMap{suffix}.json')}
                # When primary uses the main map, translations must too.
                if 'textmap_main' in bundle.files:
                    maps['textmap_main'] = request(base + f'TextMap/TextMapMain{suffix}.json')
                return language, maps, ''
            except Exception as exc:
                return language, None, f'{language} 崩鐵翻譯未取得（{type(exc).__name__}）；保留原文備援。'
        with ThreadPoolExecutor(max_workers=3) as pool:
            fetched = list(pool.map(fetch_language, LANGUAGES.items()))
        maps = {}
        for language, values, warning in fetched:
            if warning: warnings.append(warning)
            if values is not None: maps[language] = values
        overlay = build_hsr_localizations(bundle, parsed, maps, commit=commit)
        for language, counts in overlay['coverage'].items():
            for field, count in counts.items():
                if count < len(parsed.rows):
                    warnings.append(f'{language} {field} 缺少 {len(parsed.rows)-count} 筆；使用逐欄位原文備援。')
        return overlay, warnings
    except Exception as exc:
        return {}, [f'崩鐵翻譯來源版本無法確認（{type(exc).__name__}）；略過翻譯，不影響原本同步。']
