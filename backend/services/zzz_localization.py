"""Optional ZenlessData translations; reuse the primary parser and source IDs."""
from __future__ import annotations

import json
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping

REPOSITORY = 'https://git.mero.moe/dimbreath/ZenlessData'
LANGUAGES = {'en': 'EN', 'ja': 'JA', 'zh-Hans': ''}
ARCADE_PREFIXES = {'en': '[Arcade] ', 'ja': '【アーケード】', 'zh-Hans': '【街机】'}


def build_zzz_localizations(bundle: Any, parsed: Any, languages: Mapping[str, Mapping[str, Any]], *, commit: str) -> dict:
    from backend.services.game_data_sources import parse_zzz_bundle, _build_text_map, _resolve_text_with_status, _looks_like_unresolved_source_text
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Immutable source commit required')
    primary_ids = {str(row['achievement_id']) for row in parsed.rows}
    result: dict = {}
    coverage: dict = {}
    for language, maps in languages.items():
        if language not in LANGUAGES: continue
        localized = parse_zzz_bundle({**bundle.files, 'textmap': maps['textmap'],
                                      'textmap_overwrite': maps.get('textmap_overwrite', {})})
        if {str(row['achievement_id']) for row in localized.rows} != primary_ids:
            raise ValueError('Localization changed achievement IDs')
        text_map = _build_text_map(maps['textmap'], maps.get('textmap_overwrite', {}))
        counts = dict.fromkeys(('name', 'condition', 'category'), 0)
        for row in localized.rows:
            raw = json.loads(row['raw_json'])
            references = raw.get('_tracker_detected_fields', {})
            values = {}
            for field, reference in [('name', 'name'), ('condition', 'description')]:
                _, resolved = _resolve_text_with_status(raw.get(references.get(reference, '')), text_map)
                text = row.get(field) or ''
                if resolved and text and not _looks_like_unresolved_source_text(text): values[field] = text
            category = row.get('category') or ''
            if category and not re.fullmatch(r'(?:【街機】)?(?:未辨識分類|分類\s*\d+)', category):
                values['category'] = ARCADE_PREFIXES[language] + category[len('【街機】'):] if category.startswith('【街機】') else category
            reward_names = {reward['itemId']: reward['name'] for reward in raw.get('_tracker_rewards', [])
                            if isinstance(reward, dict) and reward.get('itemId') and reward.get('name')}
            if reward_names:
                values['rewardNames'] = reward_names
            if values: result.setdefault(str(row['achievement_id']), {})[language] = values
            for field in counts:
                if field in values: counts[field] += 1
        coverage[language] = counts
    return {'schema_version': 1, 'game_id': 'zzz', 'source_commit': commit,
            'items': result, 'coverage': coverage}


def fetch_zzz_localizations(bundle: Any, parsed: Any, *, timeout: int = 15,
                            request_json: Callable[[str], Any] | None = None) -> tuple[dict, list[str]]:
    from backend.services.game_data_sources import _request_bytes, _decode_json
    def request(url):
        if request_json: return request_json(url)
        raw, _ = _request_bytes(url, timeout=timeout, attempts=1, max_bytes=96*1024*1024)
        return _decode_json(raw, url=url)
    warnings = []
    try:
        if bundle.definition.game_id != 'zzz' or bundle.definition.repository_url != REPOSITORY:
            raise ValueError('Unsupported ZenlessData source')
        ref = str(bundle.source_ref or 'master')
        commit = ref if re.fullmatch(r'[0-9a-f]{40}', ref) else str(request(
            'https://git.mero.moe/api/v1/repos/dimbreath/ZenlessData/branches/' + urllib.parse.quote(ref, safe='')
        ).get('commit', {}).get('id') or '').lower()
        if not re.fullmatch(r'[0-9a-f]{40}', commit): raise ValueError('Commit unavailable')
        base = REPOSITORY + '/raw/commit/' + commit + '/'
        manifests = {row['key']: row for row in bundle.manifests}
        def verify(key):
            path = str(manifests.get(key, {}).get('path') or '')
            if not path.endswith('.json') or '..' in path or ':' in path or path.startswith('/'):
                raise ValueError('Unverified source path: ' + key)
            if request(base + path) != bundle.files[key]: raise ValueError('Source changed: ' + key)
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(verify, bundle.files))
        def fetch_language(entry):
            language, suffix = entry
            try:
                infix = suffix if not suffix else '_' + suffix
                maps = {'textmap': request(base + f'TextMap/TextMap{infix}TemplateTb.json')}
                if 'textmap_overwrite' in bundle.files:
                    maps['textmap_overwrite'] = request(base + f'TextMap/TextMap{infix}OverwriteTemplateTb.json')
                overlay = build_zzz_localizations(bundle, parsed, {language: maps}, commit=commit)
                return language, overlay, ''
            except Exception as exc:
                return language, {}, f'{language} 絕區零翻譯未取得或無法核對（{type(exc).__name__}）；保留原文備援。'
        with ThreadPoolExecutor(max_workers=3) as pool:
            fetched = list(pool.map(fetch_language, LANGUAGES.items()))
        overlay = {'schema_version': 1, 'game_id': 'zzz', 'source_commit': commit, 'items': {}, 'coverage': {}}
        for language, values, warning in fetched:
            if warning: warnings.append(warning)
            overlay['coverage'].update(values.get('coverage', {}))
            for aid, translations in values.get('items', {}).items():
                overlay['items'].setdefault(aid, {}).update(translations)
        for language, counts in overlay['coverage'].items():
            for field, count in counts.items():
                if count < len(parsed.rows): warnings.append(f'{language} {field} 缺少 {len(parsed.rows)-count} 筆；使用逐欄位原文備援。')
        return overlay, warnings
    except Exception as exc:
        return {}, [f'絕區零翻譯來源版本無法確認（{type(exc).__name__}）；略過翻譯，不影響原本同步。']
