"""Optional WW_Data translations pinned to the verified primary source commit."""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping

REPOSITORY = 'https://github.com/Arikatsu/WutheringWaves_Data'
LANGUAGES = ('en', 'ja', 'zh-Hans')


def build_wuwa_localizations(bundle: Any, parsed: Any, languages: Mapping[str, Any], *, commit: str) -> dict:
    from backend.services.game_data_sources import (
        parse_wuwa_bundle, _build_text_map, _get, _text_key, _unwrap_rows,
        _resolve_text_with_status, _looks_like_unresolved_source_text,
    )
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Immutable source commit required')
    primary_map = _build_text_map(bundle.files['textmap'])
    primary_ids = {str(row['achievement_id']) for row in parsed.rows}
    groups = {_text_key(_get(row, 'Id', 'ID', 'id')): row for row in _unwrap_rows(bundle.files['groups'])}
    items, coverage = {}, {}
    for language, payload in languages.items():
        if language not in LANGUAGES:
            continue
        text_map = _build_text_map(payload)
        # Retain primary IDs when a translated name is missing. Only fields
        # independently resolved from the original language map are exported.
        localized = parse_wuwa_bundle({**bundle.files, 'textmap': {**primary_map, **text_map}})
        if {str(row['achievement_id']) for row in localized.rows} != primary_ids:
            raise ValueError('Localization changed achievement IDs')
        counts = dict.fromkeys(('name', 'condition', 'category'), 0)
        for row in localized.rows:
            raw = json.loads(row['raw_json'])
            group = groups.get(_text_key(_get(raw, 'GroupId', 'GroupID', 'groupId', 'group_id')), {})
            references = {
                'name': _get(raw, 'Name', 'name'),
                'condition': _get(raw, 'Desc', 'Description', 'desc', 'description'),
                'category': _get(group, 'Name', 'name'),
            }
            values = {}
            for field, reference in references.items():
                text, resolved = _resolve_text_with_status(reference, text_map)
                if resolved and text and not _looks_like_unresolved_source_text(text):
                    values[field] = text
                    counts[field] += 1
            if values:
                items.setdefault(str(row['achievement_id']), {})[language] = values
        coverage[language] = counts
    return {'schema_version': 1, 'game_id': 'wuwa', 'source_commit': commit,
            'items': items, 'coverage': coverage}


def fetch_wuwa_localizations(bundle: Any, parsed: Any, *, timeout: int = 15,
                             request_json: Callable[[str], Any] | None = None,
                             cache_dir: Path | None = None) -> tuple[dict, list[str]]:
    from backend.services.localization_http_cache import request_localization_json
    def request(url):
        if request_json:
            return request_json(url)
        return request_localization_json(url, timeout=timeout, cache_dir=cache_dir)
    try:
        if bundle.definition.game_id != 'wuwa' or bundle.definition.repository_url != REPOSITORY:
            raise ValueError('Unsupported WW_Data source')
        ref = str(bundle.source_ref or '')
        if not ref:
            raise ValueError('Primary source ref required')
        commit = ref if re.fullmatch(r'[0-9a-f]{40}', ref) else str(request(
            'https://api.github.com/repos/Arikatsu/WutheringWaves_Data/commits/' + urllib.parse.quote(ref, safe='')
        ).get('sha') or '').lower()
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('Commit unavailable')
        base = 'https://raw.githubusercontent.com/Arikatsu/WutheringWaves_Data/' + commit + '/'
        manifests = {row['key']: row for row in bundle.manifests}
        def verify(key):
            path = str(manifests.get(key, {}).get('path') or '')
            if not path.endswith('.json') or '..' in path or ':' in path or path.startswith('/'):
                raise ValueError('Unverified source path: ' + key)
            if request(base + path) != bundle.files[key]:
                raise ValueError('Source changed: ' + key)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(verify, bundle.files))
        def fetch(language):
            try:
                payload = request(base + f'Textmaps/{language}/multi_text/MultiText.json')
                return build_wuwa_localizations(bundle, parsed, {language: payload}, commit=commit), ''
            except Exception as exc:
                return {}, f'{language} 鳴潮翻譯未取得或無法核對（{type(exc).__name__}）；保留原文備援。'
        with ThreadPoolExecutor(max_workers=3) as pool:
            fetched = list(pool.map(fetch, LANGUAGES))
        overlay = {'schema_version': 1, 'game_id': 'wuwa', 'source_commit': commit, 'items': {}, 'coverage': {}}
        warnings = []
        for result, warning in fetched:
            if warning:
                warnings.append(warning)
            overlay['coverage'].update(result.get('coverage', {}))
            for aid, translations in result.get('items', {}).items():
                overlay['items'].setdefault(aid, {}).update(translations)
        for language, counts in overlay['coverage'].items():
            for field, count in counts.items():
                if count < len(parsed.rows):
                    warnings.append(f'{language} {field} 缺少 {len(parsed.rows)-count} 筆；使用逐欄位原文備援。')
        return overlay, warnings
    except Exception as exc:
        return {}, [f'鳴潮翻譯來源版本無法確認（{type(exc).__name__}）；略過翻譯，不影響原本同步。']
