"""Complete ZenlessData item/title rewards, retaining IDs when text is missing."""
from __future__ import annotations

import json
from typing import Any, Mapping


def _value(row, keys, default=None):
    return next((row[key] for key in keys if key in row), default)


def reward_rows(raw: Any) -> list[dict]:
    """Public, comparable reward metadata without raw source payloads."""
    try:
        value = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        rows = value.get('_tracker_rewards', [])
        result = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get('itemId') or '').strip()
            try:
                amount = int(row.get('amount') or 0)
            except (ValueError, TypeError):
                continue
            kind = row.get('type', 'item')
            if item_id and amount > 0 and kind in ('item', 'title'):
                entry = {'itemId': item_id[:120], 'type': kind, 'amount': amount}
                if isinstance(row.get('name'), str) and row['name'].strip():
                    entry['name'] = row['name'].strip()[:200]
                result.append(entry)
        return result
    except (ValueError, TypeError):
        return []


def build_reward_index(files: Mapping[str, Any], text_map: Mapping[str, str]) -> tuple[dict, dict, dict]:
    from backend.services.game_data_sources import _unwrap_rows, _text_key, _as_int
    items = {}
    currency_ids = set()
    for row in _unwrap_rows(files.get('items')):
        item_id = _text_key(_value(row, ('PFOAJKNPCHL', 'ItemId', 'ItemID', 'Id', 'ID', 'id')))
        key = _text_key(_value(row, ('HAKHHHCAENA', 'Name', 'name', 'NameTextMapHash')))
        if item_id:
            name = str(text_map.get(key) or '').strip()
            items[item_id] = name
            # Resolve the currency by source text, not a hardcoded item ID.
            if name in {'菲林', 'Polychrome', 'ポリクローム'}:
                currency_ids.add(item_id)
    reward_index = {}
    unresolved = []
    for row in _unwrap_rows(files.get('rewards')):
        reward_id = _text_key(_value(row, ('MIBLAOBNIHP', 'PCBBLPOODAD', 'RewardID', 'RewardId', 'OnceRewardId', 'Id', 'ID', 'id')))
        entries = _value(row, ('GEHJCMHJKNA', 'PDNPHNNEOHJ', 'Items', 'items', 'RewardItems'), [])
        combined = {}
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            item_id = _text_key(_value(entry, ('HJOEBMMFOMB', 'ALLNPNDPEIE', 'ItemId', 'ItemID', 'itemId')))
            amount = _as_int(_value(entry, ('FOOIKNNLFDF', 'HBCHFGMILCM', 'Amount', 'amount', 'Count', 'count')))
            if not item_id or amount <= 0:
                continue
            if item_id not in combined:
                combined[item_id] = {'type': 'item', 'itemId': item_id, 'amount': 0}
                if items.get(item_id):
                    combined[item_id]['name'] = items[item_id]
                else:
                    unresolved.append({'reward_id': reward_id, 'item_id': item_id})
            combined[item_id]['amount'] += amount
        reward_index[reward_id] = sorted(combined.values(), key=lambda r: r['itemId'] not in currency_ids)
    titles, reverse = {}, {}
    for row in _unwrap_rows(files.get('titles')):
        title_id = _text_key(_value(row, ('GGONJJALNLA', 'TitleId', 'TitleID', 'Id', 'ID', 'id')))
        if not title_id or _as_int(title_id) <= 0:
            continue
        entry = {'type': 'title', 'itemId': 'Title_' + title_id, 'amount': 1}
        key = _text_key(_value(row, ('IOGGJNHFPLN', 'Name', 'name', 'NameTextMapHash')))
        name = str(text_map.get(key) or '').strip()
        if name:
            entry['name'] = name
        titles[title_id] = entry
        condition = _value(row, ('GCGBMEKJEMO', 'ConditionType', 'conditionType'))
        parameters = _value(row, ('IOFHFEMIPDK', 'ConditionParams', 'conditionParams'), [])
        if condition == 'TitleCondition_Achievement' and isinstance(parameters, list):
            for achievement_id in parameters:
                reverse.setdefault(_text_key(achievement_id), []).append(title_id)
    for entries in reward_index.values():
        for index, entry in enumerate(entries):
            if entry['itemId'] in titles:
                entries[index] = {**titles[entry['itemId']], 'amount': entry['amount']}
    return reward_index, {'titles': titles, 'reverse': reverse, 'items': items, 'currency_ids': currency_ids}, {
        'unresolved_item_names': unresolved, 'item_count': len(items), 'title_count': len(titles)}


def achievement_rewards(achievement_id: str, row: Mapping[str, Any], reward_id: str,
                        reward_index: dict, title_index: dict) -> list[dict]:
    from backend.services.game_data_sources import _text_key, _as_int
    result = [dict(item) for item in reward_index.get(str(reward_id), [])]
    direct = _text_key(_value(row, ('MKGHOAFAAFA', 'MKGHOAFAA', 'TitleId', 'TitleID', 'titleId')))
    title_ids = list(title_index['reverse'].get(str(achievement_id), []))
    # The current obfuscated field is an extra unlock/item reference, not
    # exclusively a title: two live rows reference commemorative profile icons.
    explicit_title = any(_as_int(row.get(key)) > 0 for key in ('TitleId', 'TitleID', 'titleId'))
    if _as_int(direct) > 0 and (direct in title_index['titles'] or explicit_title):
        title_ids.insert(0, direct)
    elif _as_int(direct) > 0 and not any(item['itemId'] == direct for item in result):
        extra = {'type': 'item', 'itemId': direct, 'amount': 1}
        if title_index['items'].get(direct):
            extra['name'] = title_index['items'][direct]
        result.append(extra)
    for title_id in dict.fromkeys(title_ids):
        if not any(item['itemId'] == 'Title_' + title_id for item in result):
            result.append(dict(title_index['titles'].get(title_id) or {
                'type': 'title', 'itemId': 'Title_' + title_id, 'amount': 1}))
    return result
