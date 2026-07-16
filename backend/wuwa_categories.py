from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

# Canonical Wuthering Waves in-game category names.
WUWA_CATEGORY_ALIASES: dict[str, str] = {
    "漂泊之旅": "漂泊之旅·一",
    "世間百態": "世間百態·一",
    "世间百态": "世間百態·一",
    "聲骸資料": "聲骸數據",
    "声骸资料": "聲骸數據",
    "聲骸数据": "聲骸數據",
    "声骸数据": "聲骸數據",
    "潮汐永珍": "潮汐萬象",
    "潮汐万象": "潮汐萬象",
}

# The known region-series order shown in the game.  A new region not listed
# here is appended after the current last region, while its footprint series
# remains directly after its matching "索拉的大地·<region>" category.
_WUWA_KNOWN_REGION_ORDER: dict[str, int] = {
    "瑝瓏": 0,
    "黑海岸": 1,
    "黎那汐塔": 2,
    # Slot 3 is reserved for the in-game special category "荒野的呼喚".
    "拉海洛": 4,
    "羅伊冰原": 5,
    "黯原": 6,
}

_WUWA_AUDIO_ORDER: dict[str, int] = {
    "成長之路": 0,
    "別域的友誼": 1,
    "聲骸數據": 2,
    "潮汐萬象": 3,
}

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "兩": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def canonicalize_wuwa_category(value: Any) -> str:
    """Return the canonical in-game category name for a Wuthering Waves row."""
    name = _clean(value).replace("鸣", "鳴").replace("珑", "瓏")
    name = re.sub(r"\s*[·•・]\s*", "·", name)
    for pattern in (
        r"^(?:官方)?成就合集[：:]\s*",
        r"^合集名稱[：:]\s*",
        r"^合集名称[：:]\s*",
        r"^合集[：:]\s*",
        r"^分類[：:]\s*",
        r"^分类[：:]\s*",
    ):
        name = re.sub(pattern, "", name).strip()
    if not name or name == "未分類":
        return "未辨識分類"
    return WUWA_CATEGORY_ALIASES.get(name, name)


def _ordinal_number(token: str) -> int:
    token = _clean(token)
    if not token:
        return 9999
    if token.isdigit():
        return int(token)
    if token in _CN_DIGITS:
        return _CN_DIGITS[token]
    if "百" in token:
        left, _, right = token.partition("百")
        hundreds = _CN_DIGITS.get(left, 1 if not left else 0)
        return hundreds * 100 + (_ordinal_number(right) if right else 0)
    if "十" in token:
        left, _, right = token.partition("十")
        tens = _CN_DIGITS.get(left, 1 if not left else 0)
        ones = _CN_DIGITS.get(right, 0 if not right else 9999)
        return tens * 10 + ones
    # Keep unrecognized suffixes after numbered entries but deterministic.
    return 9999


def _region_descriptor(category: str) -> tuple[str, int, int] | None:
    base = re.fullmatch(r"索拉的大地·(.+)", category)
    if base:
        return base.group(1), 0, 0
    footprint = re.fullmatch(r"(.+)的足跡·(.+)", category)
    if footprint:
        return footprint.group(1), 1, _ordinal_number(footprint.group(2))
    return None


def build_wuwa_category_order(categories: Iterable[Any]) -> list[str]:
    """Build the game order, including deterministic placement for new series.

    Rules:
    - A new region series is appended after the current last region series.
    - The matching footprint categories stay directly after that region base and
      are ordered by their numeric suffix.
    - Continuations such as 漂泊之旅·四 are inserted after the previous number.
    - Unknown category families preserve their first-seen order at the end.
    """
    canonical: list[str] = []
    seen: set[str] = set()
    for value in categories:
        name = canonicalize_wuwa_category(value)
        if not name or name in seen:
            continue
        seen.add(name)
        canonical.append(name)

    unknown_regions: dict[str, int] = {}
    for name in canonical:
        descriptor = _region_descriptor(name)
        if not descriptor:
            continue
        region = descriptor[0]
        if region not in _WUWA_KNOWN_REGION_ORDER and region not in unknown_regions:
            unknown_regions[region] = len(unknown_regions)

    first_seen = {name: index for index, name in enumerate(canonical)}

    def key(name: str) -> tuple[Any, ...]:
        descriptor = _region_descriptor(name)
        if descriptor:
            region, kind, ordinal = descriptor
            if region in _WUWA_KNOWN_REGION_ORDER:
                region_slot = _WUWA_KNOWN_REGION_ORDER[region]
            else:
                region_slot = 7 + unknown_regions.get(region, 9999)
            return (0, region_slot, kind, ordinal, first_seen[name])
        if name == "荒野的呼喚":
            return (0, 3, 0, 0, first_seen[name])

        match = re.fullmatch(r"漂泊之旅·(.+)", name)
        if match:
            return (1, 0, _ordinal_number(match.group(1)), first_seen[name])
        if name == "與你的印跡":
            return (1, 1, 0, first_seen[name])
        match = re.fullmatch(r"世間百態·(.+)", name)
        if match:
            return (1, 2, _ordinal_number(match.group(1)), first_seen[name])

        if name == "戰鬥的記憶":
            return (2, 0, 0, first_seen[name])
        match = re.fullmatch(r"來自深塔·(.+)", name)
        if match:
            return (2, 1, _ordinal_number(match.group(1)), first_seen[name])
        match = re.fullmatch(r"戰鬥的技巧·(.+)", name)
        if match:
            return (2, 2, _ordinal_number(match.group(1)), first_seen[name])
        if name == "戰鬥的迴響":
            return (2, 3, 0, first_seen[name])
        if name == "意外體驗":
            return (2, 4, 0, first_seen[name])

        if name in _WUWA_AUDIO_ORDER:
            return (3, _WUWA_AUDIO_ORDER[name], 0, first_seen[name])

        return (9, first_seen[name], name)

    return sorted(canonical, key=key)


def sort_wuwa_achievement_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Canonicalize categories and sort strictly by the WW_Data official ID."""
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        item = dict(row)
        item["category"] = canonicalize_wuwa_category(item.get("category"))
        achievement_id = str(item.get("id") or item.get("achievement_id") or "").strip()
        if not achievement_id.isdigit():
            raise ValueError(f"鳴潮成就缺少有效的 WW_Data 官方 ID：{achievement_id or '空白'}")
        if achievement_id in seen:
            raise ValueError(f"鳴潮 WW_Data 官方 ID 重複：{achievement_id}")
        seen.add(achievement_id)
        if "sourceOrder" in item or "source_order" not in item:
            item["sourceOrder"] = int(achievement_id)
        if "source_order" in item:
            item["source_order"] = int(achievement_id)
        normalized.append(item)
    normalized.sort(key=lambda item: (int(str(item.get("id") or item.get("achievement_id"))), str(item.get("id") or item.get("achievement_id"))))
    return normalized


# Expected current in-game order.  Kept as a validation fixture and documentation.
