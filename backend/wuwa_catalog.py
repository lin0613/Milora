from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

from backend.wuwa_categories import canonicalize_wuwa_category, sort_wuwa_achievement_rows


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["HtmlNode | str"] = field(default_factory=list)

    def element_children(self) -> list["HtmlNode"]:
        return [child for child in self.children if isinstance(child, HtmlNode)]

    def descendants(self, tags: set[str] | None = None) -> Iterable["HtmlNode"]:
        for child in self.element_children():
            if tags is None or child.tag in tags:
                yield child
            yield from child.descendants(tags)

    def find_first(self, tag: str) -> "HtmlNode | None":
        for child in self.descendants({tag}):
            return child
        return None

    def text_content(self) -> str:
        parts: list[str] = []

        def visit(node: HtmlNode | str) -> None:
            if isinstance(node, str):
                parts.append(node)
                return
            for child in node.children:
                visit(child)

        visit(self)
        return clean(" ".join(parts))

    def own_text(self) -> str:
        return clean(" ".join(child for child in self.children if isinstance(child, str)))


class SimpleHtmlTreeParser(HTMLParser):
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("root")
        self.stack: list[HtmlNode] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        node = HtmlNode(tag, {str(key): str(value or "") for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in self._VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1].tag == tag.lower() and tag.lower() not in self._VOID_TAGS:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)


_GENERIC_COLLECTION_RE = re.compile(
    r"^(?:全部成就|成就合集|官方合集|全部合集|成就一覽|成就一览|成就總覽|成就总览|"
    r"成就列表|官方成就|合集名稱|合集名称|成就分類|成就分类|全部分類|全部分类|合集|分類|分类|"
    r"類別|类别|一覽|一览|總覽|总览|列表)$"
)
_PARENT_SECTION_TITLES = {
    "索拉漫行",
    "長路留跡",
    "长路留迹",
    "鏗鏘刃鳴",
    "铿锵刃鸣",
    "諸音聲軌",
    "诸音声轨",
    "目次",
    "目錄",
    "目录",
}
_OFFICIAL_GAME_TEXT_FIXES = {
    "徒手攀巖": "徒手攀岩",
    "時間差不多咯": "時間差不多囉",
    "摩托登山家": "摩托車登山家",
    "給我幹哪兒來了？": "給我傳送到哪來了？",
    "給我幹哪兒來了": "給我傳送到哪來了？",
    "给我干哪儿来了？": "給我傳送到哪來了？",
    "给我干哪儿来了": "給我傳送到哪來了？",
    "透過《聯結之門》進行一次傳送。": "通過《聯結之門》進行一次傳送。",
    "透過《聯結之門》進行一次傳送": "通過《聯結之門》進行一次傳送。",
    "通过《联结之门》进行一次传送。": "通過《聯結之門》進行一次傳送。",
    "通过《联结之门》进行一次传送": "通過《聯結之門》進行一次傳送。",
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or "").replace("\u00a0", " "))).strip()


def strip_hidden_prefix(value: Any) -> str:
    raw = clean(value)
    stripped = re.sub(
        r"^\s*[「『【\[（(]?\s*(?:隱藏成就|隐藏成就)\s*[」』】\]）)]?\s*(?:[：:\-—·｜|]\s*)?",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()
    return stripped or raw


def normalize_official_lookup(value: Any) -> str:
    text = strip_hidden_prefix(value)
    replacements = str.maketrans(
        {
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
            "！": "!",
            "？": "?",
            "：": ":",
            "，": ",",
            "。": ".",
            "《": "<",
            "》": ">",
            "「": "(",
            "『": "(",
            "【": "(",
            "[": "(",
            "（": "(",
            "」": ")",
            "』": ")",
            "】": ")",
            "]": ")",
            "）": ")",
        }
    )
    return re.sub(r"\s+", "", text.translate(replacements)).casefold()


def fnv_achievement_id(text: str) -> str:
    value = 2166136261
    for character in text:
        value ^= ord(character)
        value = (value * 16777619) & 0xFFFFFFFF
    return f"成就-{value:x}"


def extract_exact_version(value: Any) -> str:
    text = clean(value)
    matches = re.findall(r"\d+\.\d+(?:\.\d+)?", text)
    if len(matches) != 1:
        return ""
    token = matches[0]
    short_label = re.fullmatch(
        r"(?:v(?:er(?:sion)?)?\s*|版本\s*)?\d+\.\d+(?:\.\d+)?(?:\s*版本)?",
        text,
        flags=re.IGNORECASE,
    )
    named_label = (
        bool(re.search(r"(?:版本|新增成就|更新成就)", text))
        and len(text) <= 28
        and not re.search(r"[～~至到—–-]", text)
    )
    if not short_label and not named_label:
        return ""
    parts = token.split(".")
    return f"{int(parts[0])}.{int(parts[1])}"


def is_generic_collection_label(value: Any) -> bool:
    text = re.sub(r"[：:]", "", clean(value))
    text = re.sub(r"\s+", "", text)
    return bool(_GENERIC_COLLECTION_RE.fullmatch(text))


def normalize_collection_name(value: Any) -> str:
    name = clean(value).replace("鸣", "鳴").replace("珑", "瓏")
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
    if not name or name == "未分類" or is_generic_collection_label(name):
        return "未辨識分類"
    return canonicalize_wuwa_category(name)


def is_collection_candidate(value: Any) -> bool:
    text = normalize_collection_name(value)
    if text == "未辨識分類" or text in _PARENT_SECTION_TITLES or extract_exact_version(text):
        return False
    if len(text) < 2 or len(text) > 45 or re.search(r"[。！？!?]", text):
        return False
    if re.fullmatch(r"(?:名稱|名称|版本|描述|星聲|星声|獎勵|奖励|出典|備註|备注)", text):
        return False
    return True


def is_generic_title(value: Any) -> bool:
    text = clean(value)
    return (
        not text
        or is_generic_collection_label(text)
        or text in _PARENT_SECTION_TITLES
        or bool(
            re.fullmatch(
                r"(?:成就|成就列表|全部成就|官方成就|鳴潮|鸣潮|內容|内容|說明|说明|資料|资料|表格|列表|未命名)",
                text,
                flags=re.IGNORECASE,
            )
        )
        or bool(
            re.search(
                r"(?:全成就|成就總表|成就总表|成就總覽|成就总览).*(?:\d+\.\d+.*\d+\.\d+)?",
                text,
                flags=re.IGNORECASE,
            )
        )
    )


def context_info(context: list[str], row_cells: list[str] | None = None) -> tuple[str, str]:
    row_cells = row_cells or []
    version = "未標示"
    for value in [*reversed(row_cells), *reversed(context)]:
        parsed = extract_exact_version(value)
        if parsed:
            version = parsed
            break
    collection = "未辨識分類"
    for value in reversed([clean(item) for item in context if clean(item)]):
        if (
            is_collection_candidate(value)
            and not is_generic_title(value)
            and len(re.findall(r"\d+\.\d+(?:\.\d+)?", value)) <= 1
        ):
            collection = normalize_collection_name(value)
            break
    return version, collection


def resolve_collection_name(direct_value: Any, context_value: Any) -> str:
    direct = normalize_collection_name(direct_value)
    if is_collection_candidate(direct):
        return direct
    context = normalize_collection_name(context_value)
    return context if is_collection_candidate(context) else "未辨識分類"


def reward_from(value: Any) -> int:
    text = clean(value)
    match = re.search(r"(?:星声|星聲|奖励|獎勵)[^\d]{0,8}(5|10|20)(?!\d)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(?:×|x|\*)\s*(5|10|20)(?!\d)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _map_header(cells: list[str]) -> dict[str, int]:
    lowered = [clean(value).lower() for value in cells]

    def find(pattern: str) -> int:
        for index, value in enumerate(lowered):
            if re.search(pattern, value):
                return index
        return -1

    return {
        "name": find(r"成就.*(名|名稱|名称)|^(名稱|名称|成就)$"),
        "condition": find(r"達成|达成|完成.*條件|完成.*条件|條件|条件|描述|說明|说明"),
        "reward": find(r"星聲|星声|獎勵|奖励"),
        "version": find(r"版本"),
        "category": find(r"成就合集|合集|系列"),
        "subcategory": find(r"子分類|子分类|小分類|小分类|細分|细分"),
        "hidden": find(r"隱藏|隐藏"),
    }


def _has_useful_header(header: dict[str, int]) -> bool:
    return any(header[key] >= 0 for key in ("name", "condition", "reward", "version"))


def _make_achievement(
    *,
    name: Any,
    condition: Any,
    reward: Any = 0,
    hidden: Any = False,
    version: Any = "未標示",
    category: Any = "未分類",
    source_order: int = 0,
    achievement_id: str = "",
) -> dict[str, Any] | None:
    normalized_name = clean(name)
    normalized_condition = clean(condition)
    if (
        not normalized_name
        or not normalized_condition
        or normalized_name == normalized_condition
        or len(normalized_name) > 120
        or len(normalized_condition) > 800
    ):
        return None
    normalized_version = extract_exact_version(version) or "未標示"
    return {
        "id": clean(achievement_id) or fnv_achievement_id(f"{normalized_name}|{normalized_condition}"),
        "name": normalized_name,
        "condition": normalized_condition,
        "version": normalized_version,
        "category": normalize_collection_name(category),
        "reward": int(reward or 0),
        "hidden": bool(hidden),
        "tags": [],
        "source": "kuro-official-wiki",
        "sourceOrder": int(source_order),
    }


def _choice_cell_parts(cell: HtmlNode, fallback_text: str) -> list[str]:
    parts = [child.text_content() for child in cell.element_children()]
    parts = [value for value in parts if value and not re.fullmatch(r"(?:或|or)", value, flags=re.IGNORECASE)]
    if len(parts) < 2:
        parts = [clean(value) for value in re.split(r"\s+(?:或|or)\s+", clean(fallback_text), flags=re.IGNORECASE)]
        parts = [value for value in parts if value]
    return parts


def _parse_table(table: HtmlNode, context: list[str], collector: list[dict[str, Any]], order_ref: list[int]) -> None:
    records: list[tuple[HtmlNode, list[str]]] = []
    for row in table.descendants({"tr"}):
        cells = [child.text_content() for child in row.element_children() if child.tag in {"th", "td"}]
        if any(cells):
            records.append((row, cells))
    if len(records) < 2:
        return

    header = _map_header(records[0][1])
    start = 1 if _has_useful_header(header) else 0
    for row, cells in records[start:]:
        if len(cells) < 2:
            continue
        name = ""
        condition = ""
        version = ""
        category = ""
        reward = 0
        hidden = False
        if _has_useful_header(header):
            name = cells[header["name"]] if 0 <= header["name"] < len(cells) else ""
            condition = cells[header["condition"]] if 0 <= header["condition"] < len(cells) else ""
            reward = (
                reward_from(cells[header["reward"]])
                if 0 <= header["reward"] < len(cells)
                else reward_from(" ".join(cells))
            )
            version = cells[header["version"]] if 0 <= header["version"] < len(cells) else ""
            category = cells[header["category"]] if 0 <= header["category"] < len(cells) else ""
            if is_generic_collection_label(category):
                category = ""
            hidden = (
                bool(re.search(r"是|隱藏|隐藏|yes", cells[header["hidden"]], flags=re.IGNORECASE))
                if 0 <= header["hidden"] < len(cells)
                else any(re.search(r"隱藏成就|隐藏成就", cell) for cell in cells)
            )
        else:
            reward_index = -1
            for index, cell in enumerate(cells):
                if re.fullmatch(r"(?:5|10|20)", cell) or re.search(
                    r"(?:星声|星聲|×|x|\*)\s*(5|10|20)", cell, flags=re.IGNORECASE
                ):
                    reward_index = index
            reward = (
                reward_from(f"星聲 {cells[reward_index]}")
                if reward_index >= 0
                else reward_from(" ".join(cells))
            )
            version_index = next((index for index, cell in enumerate(cells) if extract_exact_version(cell)), -1)
            if version_index >= 0:
                version = extract_exact_version(cells[version_index])
            usable = [
                cell
                for index, cell in enumerate(cells)
                if index not in {reward_index, version_index}
                and not re.fullmatch(r"(?:是|否|隱藏|隐藏)", cell)
            ]
            name = usable[0] if usable else ""
            condition = sorted(usable[1:], key=len, reverse=True)[0] if len(usable) > 1 else ""
            hidden = any(re.search(r"隱藏|隐藏", cell) for cell in cells)

        context_version, context_category = context_info(context, cells)
        resolved_category = resolve_collection_name(category, context_category)
        row_tag = clean(row.attrs.get("data-filter-tag", ""))
        if re.search(r"特殊-(?:二|三|多)[選选]一", row_tag):
            cell_nodes = [child for child in row.element_children() if child.tag in {"th", "td"}]
            if cell_nodes:
                name_cell = cell_nodes[header["name"]] if 0 <= header["name"] < len(cell_nodes) else cell_nodes[0]
                condition_index = header["condition"] if header["condition"] >= 0 else min(3, len(cell_nodes) - 1)
                condition_cell = cell_nodes[condition_index]
                names = _choice_cell_parts(name_cell, name)
                conditions = _choice_cell_parts(condition_cell, condition)
                if len(names) >= 2 and len(names) == len(conditions):
                    for choice_name, choice_condition in zip(names, conditions):
                        item = _make_achievement(
                            name=choice_name,
                            condition=choice_condition,
                            reward=reward,
                            hidden=True,
                            version=version or context_version,
                            category=resolved_category,
                            source_order=order_ref[0],
                        )
                        order_ref[0] += 1
                        if item:
                            collector.append(item)
                    continue

        item = _make_achievement(
            name=name,
            condition=condition,
            reward=reward,
            hidden=hidden,
            version=version or context_version,
            category=resolved_category,
            source_order=order_ref[0],
        )
        order_ref[0] += 1
        if item:
            collector.append(item)


def _heading_text(node: HtmlNode) -> str:
    if re.fullmatch(r"h[1-6]", node.tag) or node.tag == "caption":
        return node.text_content()
    if node.tag in {"strong", "b", "p"}:
        text = node.text_content()
        return text if len(text) <= 45 else ""
    if node.tag in {"div", "section"}:
        text = node.own_text()
        return text if len(text) <= 45 else ""
    return ""


def _parse_html(value: str, context: list[str], collector: list[dict[str, Any]], order_ref: list[int]) -> None:
    parser = SimpleHtmlTreeParser()
    parser.feed(value)
    current_context = list(context)

    def visit(node: HtmlNode) -> None:
        nonlocal current_context
        if node.tag == "table":
            caption = node.find_first("caption")
            caption_text = caption.text_content() if caption else ""
            table_context = [*current_context, caption_text] if caption_text and is_collection_candidate(caption_text) else current_context
            _parse_table(node, table_context, collector, order_ref)
            return
        candidate = _heading_text(node)
        if candidate and is_collection_candidate(candidate):
            current_context = [*context, candidate]
        for child in node.element_children():
            visit(child)

    for child in parser.root.element_children():
        visit(child)


def _probable_title(value: dict[str, Any]) -> str:
    for key in (
        "tabName",
        "moduleName",
        "groupName",
        "sectionName",
        "collectionName",
        "collectionTitle",
        "categoryName",
        "optionalTitle",
        "titleMore",
        "label",
    ):
        candidate = value.get(key)
        if isinstance(candidate, str) and is_collection_candidate(candidate):
            return normalize_collection_name(candidate)
    return ""


def _value_by_keys(value: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and clean(candidate):
            return clean(candidate)
    return ""


def _walk_payload(
    node: Any,
    context: list[str],
    collector: list[dict[str, Any]],
    order_ref: list[int],
    seen: set[int],
) -> None:
    if node is None:
        return
    if isinstance(node, str):
        if re.search(r"<table[\s>]", node, flags=re.IGNORECASE):
            _parse_html(node, context, collector, order_ref)
        return
    if not isinstance(node, (dict, list)):
        return
    identity = id(node)
    if identity in seen:
        return
    seen.add(identity)
    if isinstance(node, list):
        for child in node:
            _walk_payload(child, context, collector, order_ref, seen)
        return

    name = _value_by_keys(node, ("achievementName", "trophyName", "name", "title"))
    condition = _value_by_keys(
        node,
        ("achievementDesc", "trophyDesc", "condition", "description", "desc", "requirement", "targetDescription"),
    )
    is_achievement = bool(name and condition and not re.search(r"<[a-z][\s\S]*>", condition, flags=re.IGNORECASE))
    title = "" if is_achievement else _probable_title(node)
    next_context = [*context, title] if title and title not in context else context
    if is_achievement:
        context_version, context_category = context_info(next_context)
        reward = int(node.get("reward") or node.get("astrite") or node.get("starSound") or node.get("score") or 0)
        if not reward:
            reward = reward_from(json.dumps(node, ensure_ascii=False))
        hidden = bool(node.get("hidden") or node.get("isHidden") or node.get("hide")) or bool(
            re.search(r"隱藏|隐藏", json.dumps(node, ensure_ascii=False)[:500])
        )
        direct_collection = (
            node.get("collectionName")
            or node.get("achievementCollection")
            or node.get("collectionTitle")
            or node.get("groupName")
            or node.get("categoryName")
            or node.get("mainCategory")
            or ""
        )
        item = _make_achievement(
            name=name,
            condition=condition,
            reward=reward,
            hidden=hidden,
            version=extract_exact_version(node.get("version") or node.get("gameVersion") or "") or context_version,
            category=resolve_collection_name(direct_collection, context_category),
            source_order=order_ref[0],
        )
        order_ref[0] += 1
        if item:
            collector.append(item)
    for child in node.values():
        if isinstance(child, str) and re.search(r"<table[\s>]", child, flags=re.IGNORECASE):
            _parse_html(child, next_context, collector, order_ref)
        elif isinstance(child, (dict, list)):
            _walk_payload(child, next_context, collector, order_ref, seen)


def _one_edit_apart(left: str, right: str) -> bool:
    left = normalize_official_lookup(left)
    right = normalize_official_lookup(right)
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) == 1
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    i = 0
    j = 0
    skipped = 0
    while i < len(shorter) and j < len(longer):
        if shorter[i] == longer[j]:
            i += 1
            j += 1
            continue
        skipped += 1
        if skipped > 1:
            return False
        j += 1
    return True


def _unique_alias_map(rows: list[dict[str, Any]], extractor) -> dict[str, dict[str, Any] | None]:
    result: dict[str, dict[str, Any] | None] = {}
    for row in rows:
        for value in extractor(row):
            key = normalize_official_lookup(value)
            if not key:
                continue
            if key not in result:
                result[key] = row
            elif result[key] is not row:
                result[key] = None
    return result


def _official_aliases(row: dict[str, Any], prefix: str) -> list[str]:
    values: list[str] = []
    aliases = row.get(f"{prefix}_aliases")
    if isinstance(aliases, list):
        values.extend(clean(item) for item in aliases if clean(item))
    keys = (
        ("zh_hans_name", "source_tw_name", "zh_hant_name")
        if prefix == "name"
        else ("zh_hans_condition", "source_tw_condition", "zh_hant_condition")
    )
    for key in keys:
        value = clean(row.get(key))
        if value and value not in values:
            values.append(value)
    return values


def apply_official_traditional_text(
    items: list[dict[str, Any]], official_payload: dict[str, Any] | None
) -> list[dict[str, Any]]:
    records = official_payload.get("records") if isinstance(official_payload, dict) else None
    if not isinstance(records, list):
        return items
    rows = [row for row in records if isinstance(row, dict)]
    name_map = _unique_alias_map(rows, lambda row: _official_aliases(row, "name"))
    condition_map = _unique_alias_map(rows, lambda row: _official_aliases(row, "condition"))
    pair_map: dict[str, dict[str, Any] | None] = {}
    for row in rows:
        for name in _official_aliases(row, "name"):
            name_key = normalize_official_lookup(name)
            for condition in _official_aliases(row, "condition"):
                key = f"{name_key}|{normalize_official_lookup(condition)}"
                if key not in pair_map:
                    pair_map[key] = row
                elif pair_map[key] is not row:
                    pair_map[key] = None

    def find_row(item: dict[str, Any]) -> dict[str, Any] | None:
        name = strip_hidden_prefix(item.get("name"))
        condition = clean(item.get("condition"))
        name_key = normalize_official_lookup(name)
        condition_key = normalize_official_lookup(condition)
        matched = pair_map.get(f"{name_key}|{condition_key}")
        if matched:
            return matched
        matched = name_map.get(name_key)
        if matched:
            return matched
        matched = condition_map.get(condition_key)
        if matched:
            return matched
        if len(name_key) < 3:
            return None
        found: dict[str, Any] | None = None
        for row in rows:
            if not any(_one_edit_apart(name_key, alias) for alias in _official_aliases(row, "name")):
                continue
            if found is not None and found is not row:
                return None
            found = row
        return found

    output: list[dict[str, Any]] = []
    for item in items:
        updated = dict(item)
        row = find_row(item)
        if row:
            display_name = strip_hidden_prefix(row.get("zh_hant_name") or item.get("name"))
            display_condition = clean(row.get("zh_hant_condition") or item.get("condition"))
            updated["name"] = _OFFICIAL_GAME_TEXT_FIXES.get(display_name, display_name)
            updated["condition"] = _OFFICIAL_GAME_TEXT_FIXES.get(display_condition, display_condition)
        else:
            visible_name = strip_hidden_prefix(item.get("name"))
            updated["name"] = _OFFICIAL_GAME_TEXT_FIXES.get(visible_name, visible_name)
            condition = clean(item.get("condition"))
            updated["condition"] = _OFFICIAL_GAME_TEXT_FIXES.get(condition, condition)
        output.append(updated)
    return output


def extract_wuwa_achievements(
    payload: Any,
    official_traditional_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    collector: list[dict[str, Any]] = []
    _walk_payload(payload, [], collector, [0], set())
    by_key: dict[str, dict[str, Any]] = {}
    for item in collector:
        key = f"{clean(item['name']).casefold()}|{clean(item['condition']).casefold()}"
        if key not in by_key:
            by_key[key] = item
            continue
        current = by_key[key]
        if current["version"] == "未標示" and item["version"] != "未標示":
            current["version"] = item["version"]
        if not is_collection_candidate(current["category"]) and is_collection_candidate(item["category"]):
            current["category"] = normalize_collection_name(item["category"])
        if not current["reward"] and item["reward"]:
            current["reward"] = item["reward"]
        if item["hidden"]:
            current["hidden"] = True
    rows = sorted(by_key.values(), key=lambda item: int(item.get("sourceOrder") or 0))
    rows = apply_official_traditional_text(rows, official_traditional_payload)
    rows = sort_wuwa_achievement_rows(rows)
    if len(rows) < 1000:
        raise ValueError(f"鳴潮官方成就只解析到 {len(rows)} 筆，已拒絕更新共用目錄。")
    category_count = len({item["category"] for item in rows if is_collection_candidate(item["category"])})
    recognized = sum(1 for item in rows if is_collection_candidate(item["category"]))
    if category_count < 3 or recognized / len(rows) < 0.6:
        raise ValueError("鳴潮官方成就合集解析不足，已拒絕更新共用目錄。")
    return rows


def build_wuwa_catalog_file(
    raw_file: Path,
    output_file: Path,
    official_traditional_file: Path | None = None,
    source: str = "https://wiki.kurobbs.com/mc/item/1220879855033786368",
) -> dict[str, Any]:
    payload = json.loads(raw_file.read_text(encoding="utf-8-sig"))
    traditional_payload: dict[str, Any] | None = None
    if official_traditional_file and official_traditional_file.exists():
        value = json.loads(official_traditional_file.read_text(encoding="utf-8-sig"))
        if isinstance(value, dict):
            traditional_payload = value
    rows = extract_wuwa_achievements(payload, traditional_payload)
    document = {
        "schema_version": 1,
        "game_id": "wuwa",
        "source": source,
        "count": len(rows),
        "items": rows,
    }
    temp_file = output_file.with_suffix(output_file.suffix + ".tmp")
    temp_file.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(output_file)
    return document
