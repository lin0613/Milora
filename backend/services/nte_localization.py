"""Optional NTE_Assets translations pinned to the verified primary source commit."""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping

REPOSITORY = 'https://github.com/Waifus-Grace/NTE_Assets'
LANGUAGES = ('en', 'ja', 'zh-Hans')


def build_nte_localizations(bundle: Any, parsed: Any, languages: Mapping[str, Any], *, commit: str) -> dict:
    from backend.services.game_data_sources import parse_nte_bundle, _nte_localized_text, NTE_CATEGORY_NAMES
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Immutable source commit required')
    primary_ids = {str(row['achievement_id']) for row in parsed.rows}
    items, coverage = {}, {}
    for language, payload in languages.items():
        if language not in LANGUAGES:
            continue
        text_map = _nte_localized_text(payload)
        if not text_map:
            raise ValueError('Missing ST_Achievement namespace')
        # The existing parser controls IDs and PlayStation exclusions.
        localized = parse_nte_bundle({**bundle.files, 'localization_zh_hant': payload})
        if {str(row['achievement_id']) for row in localized.rows} != primary_ids:
            raise ValueError('Localization changed achievement IDs')
        ui_text = payload.get('ST_Ui', {}) if isinstance(payload, dict) else {}
        counts = dict.fromkeys(('name', 'condition', 'category'), 0)
        for row in localized.rows:
            raw = json.loads(row['raw_json'])
            references = raw.get('_tracker_text_resolution', {})
            values = {}
            reward_names = {reward['itemId']: reward['name']
                            for reward in raw.get('_tracker_rewards', [])
                            if isinstance(reward, dict) and isinstance(reward.get('name'), str) and reward['name'].strip()}
            if reward_names:
                values['rewardNames'] = reward_names
            for field, key in [('name', 'titleKey'), ('condition', 'contentKey')]:
                text = str(text_map.get(references.get(key)) or '').strip()
                if text:
                    values[field] = text
                    counts[field] += 1
            main_type = str(raw.get('AchievementMainType') or '').split('::')[-1].strip()
            if main_type in NTE_CATEGORY_NAMES and isinstance(ui_text, dict):
                key = 'Achievement_' + main_type[len('MainType'):]
                title = ui_text.get(key)
                nickname = ui_text.get(key + '_Nickname')
                if isinstance(title, str) and title.strip() and isinstance(nickname, str) and nickname.strip():
                    values['category'] = title.strip() + '｜' + nickname.strip()
                    counts['category'] += 1
            if values:
                items.setdefault(str(row['achievement_id']), {})[language] = values
        coverage[language] = counts
    return {'schema_version': 1, 'game_id': 'nte', 'source_commit': commit,
            'items': items, 'coverage': coverage}


def fetch_nte_localizations(bundle: Any, parsed: Any, *, timeout: int = 15,
                             request_json: Callable[[str], Any] | None = None,
                             cache_dir: Path | None = None) -> tuple[dict, list[str]]:
    from backend.services.localization_http_cache import request_localization_json
    def request(url):
        if request_json:
            return request_json(url)
        return request_localization_json(url, timeout=timeout, cache_dir=cache_dir)
    try:
        if bundle.definition.game_id != 'nte' or bundle.definition.repository_url != REPOSITORY:
            raise ValueError('Unsupported NTE_Assets source')
        ref = str(bundle.source_ref or '')
        if not ref:
            raise ValueError('Primary source ref required')
        commit = ref if re.fullmatch(r'[0-9a-f]{40}', ref) else str(request(
            'https://api.github.com/repos/Waifus-Grace/NTE_Assets/commits/' + urllib.parse.quote(ref, safe='')
        ).get('sha') or '').lower()
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('Commit unavailable')
        base = 'https://raw.githubusercontent.com/Waifus-Grace/NTE_Assets/' + commit + '/'
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
                payload = request(base + f'Localization/{language}/game.json')
                return build_nte_localizations(bundle, parsed, {language: payload}, commit=commit), ''
            except Exception as exc:
                return {}, f'{language} 異環翻譯未取得或無法核對（{type(exc).__name__}）；保留原文備援。'
        with ThreadPoolExecutor(max_workers=3) as pool:
            fetched = list(pool.map(fetch, LANGUAGES))
        overlay = {'schema_version': 1, 'game_id': 'nte', 'source_commit': commit, 'items': {}, 'coverage': {}}
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
        return {}, [f'異環翻譯來源版本無法確認（{type(exc).__name__}）；略過翻譯，不影響原本同步。']
