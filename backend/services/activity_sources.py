from __future__ import annotations

import html
import json
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from opencc import OpenCC
except ImportError:
    class OpenCC:  # type: ignore[override]
        def __init__(self, _: str):
            pass

        def convert(self, value: str) -> str:
            return value

from backend.services.activity_todo import event_content_hash


MAX_RESPONSE_BYTES = 8 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 20
RECENT_CANDIDATE_WINDOW_SECONDS = 180 * 24 * 60 * 60
TAIPEI = "Asia/Taipei"
TRADITIONAL_CONVERTER = OpenCC("s2twp")
HOYOVERSE_CHANNEL_IDS: dict[str, tuple[str, ...]] = {
    "genshin": ("396", "397", "398"),
    "hsr": ("249", "250", "251"),
    "zzz": ("295", "296", "297"),
}
HOYOVERSE_EVENT_CHANNEL_IDS: dict[str, frozenset[str]] = {
    "genshin": frozenset({"398"}),
    "hsr": frozenset({"251"}),
    "zzz": frozenset({"297"}),
}


@dataclass(frozen=True)
class OfficialSource:
    id: str
    game_id: str
    name: str
    official_url: str
    fetch_url: str
    allowed_hosts: tuple[str, ...]
    parser: str
    detail_url_template: str


# Sources are added and verified in the product order requested by the owner.
OFFICIAL_SOURCES: tuple[OfficialSource, ...] = (
    OfficialSource(
        id="genshin-official-zh-tw",
        game_id="genshin",
        name="《原神》官方網站（繁體中文）",
        official_url="https://genshin.hoyoverse.com/zh-tw/news",
        fetch_url=(
            "https://sg-public-api-static.hoyoverse.com/content_v2_user/app/"
            "a1b1f9d3315447cc/getContentList?iAppId=32&iChanId=395&"
            "iPageSize=50&iPage=1&sLangKey=zh-tw"
        ),
        allowed_hosts=("sg-public-api-static.hoyoverse.com",),
        parser="hoyoverse_content_v2",
        detail_url_template="https://genshin.hoyoverse.com/zh-tw/news/detail/{source_key}",
    ),
    OfficialSource(
        id="hsr-official-zh-tw",
        game_id="hsr",
        name="《崩壞：星穹鐵道》官方網站（繁體中文）",
        official_url="https://hsr.hoyoverse.com/zh-tw/news",
        fetch_url=(
            "https://sg-public-api-static.hoyoverse.com/content_v2_user/app/"
            "113fe6d3b4514cdd/getContentList?iChanId=248&iPage=1&"
            "iPageSize=50&sLangKey=zh-tw"
        ),
        allowed_hosts=("sg-public-api-static.hoyoverse.com",),
        parser="hoyoverse_content_v2",
        detail_url_template="https://hsr.hoyoverse.com/zh-tw/news/{source_key}",
    ),
    OfficialSource(
        id="zzz-official-zh-tw",
        game_id="zzz",
        name="《絕區零》官方網站（繁體中文）",
        official_url="https://zenless.hoyoverse.com/zh-tw/news",
        fetch_url=(
            "https://sg-public-api-static.hoyoverse.com/content_v2_user/app/"
            "3e9196a4b9274bd7/getContentList?iChanId=288&iPage=1&"
            "iPageSize=50&sLangKey=zh-tw"
        ),
        allowed_hosts=("sg-public-api-static.hoyoverse.com",),
        parser="hoyoverse_content_v2",
        detail_url_template="https://zenless.hoyoverse.com/zh-tw/news/{source_key}",
    ),
    OfficialSource(
        id="wuwa-official-zh-tw",
        game_id="wuwa",
        name="《鳴潮》官方網站（繁體中文）",
        official_url="https://wutheringwaves.kurogames.com/zh-tw/main/news",
        fetch_url=(
            "https://hw-media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/"
            "json/G152/zh-tw/MainMenu.json"
        ),
        allowed_hosts=("hw-media-cdn-mingchao.kurogame.com",),
        parser="kuro_static_json",
        detail_url_template="https://wutheringwaves.kurogames.com/zh-tw/main/news/detail/{source_key}",
    ),
    OfficialSource(
        id="nte-official-zh-tw",
        game_id="nte",
        name="《異環》台港澳官方網站（繁體中文）",
        official_url="https://nte.iwplay.com.tw/news/list_1.html",
        fetch_url="https://nte.iwplay.com.tw/news/indexS_3.html",
        allowed_hosts=("nte.iwplay.com.tw",),
        parser="iwplay_html",
        detail_url_template="https://nte.iwplay.com.tw/news/view/{source_key}.html",
    ),
    OfficialSource(
        id="endfield-official-zh-tw",
        game_id="endfield",
        name="《明日方舟：終末地》官方網站（繁體中文）",
        official_url="https://endfield.gryphline.com/zh-tw/news",
        fetch_url="https://endfield.gryphline.com/zh-tw/news",
        allowed_hosts=("endfield.gryphline.com", "web-news.gryphline.com"),
        parser="gryphline_next_html",
        detail_url_template="https://endfield.gryphline.com/zh-tw/news/{source_key}",
    ),
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.parts.append(value)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _taipei_zone():
    try:
        return ZoneInfo(TAIPEI)
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().tzinfo or UTC


def source_for_game(game_id: str) -> OfficialSource:
    normalized = str(game_id or "").strip().lower()
    source = next((item for item in OFFICIAL_SOURCES if item.game_id == normalized), None)
    if source is None:
        raise LookupError("這款遊戲的官方活動來源尚未接入。")
    return source


def ensure_sources(db: sqlite3.Connection, stamp: int) -> None:
    for source in OFFICIAL_SOURCES:
        db.execute(
            """insert into activity_sources(
            id,game_id,name,source_type,official_url,fetch_url,language,enabled,
            auto_publish_safe,last_error,created_at,updated_at)
            values(?,?,?,'official_web',?,?,'zh-TW',1,1,'',?,?)
            on conflict(id) do update set
            game_id=excluded.game_id,name=excluded.name,official_url=excluded.official_url,
            fetch_url=excluded.fetch_url,language='zh-TW',enabled=1,updated_at=excluded.updated_at
            where activity_sources.game_id<>excluded.game_id
            or activity_sources.name<>excluded.name
            or activity_sources.official_url<>excluded.official_url
            or activity_sources.fetch_url<>excluded.fetch_url
            or activity_sources.language<>'zh-TW'
            or activity_sources.enabled<>1""",
            (
                source.id,
                source.game_id,
                source.name,
                source.official_url,
                source.fetch_url,
                stamp,
                stamp,
            ),
        )


def _validated_url(url: str, source: OfficialSource) -> str:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("官方來源必須使用不含帳密的 HTTPS 網址。")
    if parsed.port not in (None, 443):
        raise ValueError("官方來源不可使用非標準連接埠。")
    if host not in source.allowed_hosts:
        raise ValueError("官方來源重新導向到未授權的網域。")
    return urllib.parse.urlunsplit(parsed)


def _fetch_json_url(source: OfficialSource, url: str) -> dict[str, Any]:
    current_url = _validated_url(url, source)
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(4):
        request = urllib.request.Request(
            current_url,
            headers={
                "Accept": "application/json",
                "Accept-Language": "zh-TW,zh;q=0.9",
                "User-Agent": "Milora-Activity-Tracker/1.0 (+https://miloratool.tdvr.tw)",
            },
        )
        try:
            response = opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as exc:
            if exc.code not in {301, 302, 303, 307, 308}:
                raise RuntimeError(f"官方來源回應 HTTP {exc.code}。") from exc
            location = exc.headers.get("Location", "")
            if not location:
                raise RuntimeError("官方來源回傳無效的重新導向。") from exc
            current_url = _validated_url(urllib.parse.urljoin(current_url, location), source)
            continue
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "json" not in content_type:
            raise RuntimeError("官方來源未回傳 JSON。")
        declared_length = int(response.headers.get("Content-Length") or 0)
        if declared_length > MAX_RESPONSE_BYTES:
            raise RuntimeError("官方來源回應超過安全大小限制。")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("官方來源回應超過安全大小限制。")
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("官方來源 JSON 無法解析。") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("官方來源資料格式不正確。")
        return payload
    raise RuntimeError("官方來源重新導向次數過多。")


def _fetch_text_url(source: OfficialSource, url: str) -> str:
    current_url = _validated_url(url, source)
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(4):
        request = urllib.request.Request(
            current_url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-TW,zh;q=0.9",
                "User-Agent": "Milora-Activity-Tracker/1.0 (+https://miloratool.tdvr.tw)",
            },
        )
        try:
            response = opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as exc:
            if exc.code not in {301, 302, 303, 307, 308}:
                raise RuntimeError(f"官方來源回應 HTTP {exc.code}。") from exc
            location = exc.headers.get("Location", "")
            if not location:
                raise RuntimeError("官方來源回傳無效的重新導向。") from exc
            current_url = _validated_url(urllib.parse.urljoin(current_url, location), source)
            continue
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "html" not in content_type and "text" not in content_type:
            raise RuntimeError("官方來源未回傳網頁內容。")
        declared_length = int(response.headers.get("Content-Length") or 0)
        if declared_length > MAX_RESPONSE_BYTES:
            raise RuntimeError("官方來源回應超過安全大小限制。")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("官方來源回應超過安全大小限制。")
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            return raw.decode("utf-8-sig", errors="replace")
    raise RuntimeError("官方來源重新導向次數過多。")


def _iwplay_entries(fragment: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"<a[^>]+class=[\"'][^\"']*intelSlideTit[^\"']*[\"'][^>]+"
        r"href=[\"'](?P<href>[^\"']+)[\"'][^>]+title=[\"'](?P<title>[^\"']+)[\"']",
        re.IGNORECASE,
    )
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in pattern.finditer(fragment):
        href = html.unescape(match.group("href")).strip()
        title = TRADITIONAL_CONVERTER.convert(html.unescape(match.group("title")).strip())
        if not href or href in seen or not title:
            continue
        entries.append({"href": href, "title": title})
        seen.add(href)
    return entries


def _decode_next_rsc_json(page: str, key: str, terminator: str) -> Any:
    match = re.search(
        rf'\\"{re.escape(key)}\\":(?P<value>.*?){re.escape(terminator)}',
        page,
        re.DOTALL,
    )
    if match is None:
        raise RuntimeError("終末地官方來源缺少公告資料。")
    try:
        decoded = json.loads(f'"{match.group("value")}"')
        return json.loads(decoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("終末地官方來源公告資料無法解析。") from exc


def _gryphline_entries(page: str) -> list[dict[str, Any]]:
    rows = _decode_next_rsc_json(page, "bulletins", r',\"total\"')
    if not isinstance(rows, list):
        raise RuntimeError("終末地官方來源缺少公告清單。")
    return [row for row in rows if isinstance(row, dict)]


def fetch_official_json(source: OfficialSource) -> dict[str, Any]:
    if source.parser == "iwplay_html":
        event_fragment = _fetch_text_url(source, source.fetch_url)
        system_url = source.fetch_url.rsplit("/", 1)[0] + "/indexS_2.html"
        system_fragment = _fetch_text_url(source, system_url)
        entries = [
            {**entry, "source_category": "activity"}
            for entry in _iwplay_entries(event_fragment)
        ] + [
            {**entry, "source_category": "system"}
            for entry in _iwplay_entries(system_fragment)
        ]
        unique_entries: list[dict[str, str]] = []
        seen: set[str] = set()
        details: dict[str, str] = {}
        for entry in entries:
            detail_url = _validated_url(urllib.parse.urljoin(source.official_url, entry["href"]), source)
            parsed = urllib.parse.urlsplit(detail_url)
            source_key = parsed.path.removeprefix("/news/view/").removesuffix(".html").strip("/")
            if (
                not source_key
                or source_key in seen
                or (
                    entry.get("source_category") != "activity"
                    and not _is_relevant_title(entry["title"])
                )
            ):
                continue
            details[source_key] = _fetch_text_url(source, detail_url)
            unique_entries.append({**entry, "source_key": source_key, "official_url": detail_url})
            seen.add(source_key)
        if not details:
            raise RuntimeError("異環官方來源沒有可讀取的近期活動公告；已保留既有資料。")
        return {"entries": unique_entries, "__details": details}
    if source.parser == "gryphline_next_html":
        api_base = "https://web-news.gryphline.com/api/bulletin"
        rows: list[dict[str, Any]] = []
        seen_rows: set[str] = set()
        for tab in ("events", "notices"):
            list_url = f"{api_base}?" + urllib.parse.urlencode(
                {
                    "lang": "zh-tw",
                    "code": "arknights_endfield_official",
                    "page": "1",
                    "pageSize": "50",
                    "tabs[]": tab,
                }
            )
            list_payload = _fetch_json_url(source, list_url)
            if list_payload.get("code") not in (0, "0"):
                raise RuntimeError("終末地官方公告分類讀取失敗。")
            data = list_payload.get("data")
            tab_rows = data.get("list") if isinstance(data, dict) else None
            if not isinstance(tab_rows, list):
                raise RuntimeError("終末地官方來源缺少公告分類清單。")
            for row in tab_rows:
                if not isinstance(row, dict):
                    continue
                source_key = str(row.get("cid") or "").strip()
                if not source_key or source_key in seen_rows:
                    continue
                rows.append(row)
                seen_rows.add(source_key)
        details: dict[str, dict[str, Any]] = {}
        for row in rows:
            source_key = str(row.get("cid") or "").strip()
            title = TRADITIONAL_CONVERTER.convert(str(row.get("title") or "").strip())
            if (
                not source_key
                or not source_key.isdigit()
                or (str(row.get("tab") or "") != "events" and not _is_relevant_title(title))
            ):
                continue
            detail_url = f"{api_base}/{urllib.parse.quote(source_key, safe='')}?" + urllib.parse.urlencode(
                {"lang": "zh-tw", "code": "arknights_endfield_official"}
            )
            detail_payload = _fetch_json_url(source, detail_url)
            detail = detail_payload.get("data") if detail_payload.get("code") in (0, "0") else None
            if isinstance(detail, dict):
                details[source_key] = detail
        if not details:
            raise RuntimeError("終末地官方來源沒有可讀取的近期活動公告；已保留既有資料。")
        return {"bulletins": rows, "__details": details}
    if source.parser == "hoyoverse_content_v2" and source.game_id in HOYOVERSE_CHANNEL_IDS:
        parsed_url = urllib.parse.urlsplit(source.fetch_url)
        base_query = dict(urllib.parse.parse_qsl(parsed_url.query, keep_blank_values=True))
        combined: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for channel_id in HOYOVERSE_CHANNEL_IDS[source.game_id]:
            query = {**base_query, "iChanId": channel_id, "iPage": "1", "iPageSize": "50"}
            channel_url = urllib.parse.urlunsplit(
                (parsed_url.scheme, parsed_url.netloc, parsed_url.path, urllib.parse.urlencode(query), "")
            )
            channel_payload = _fetch_json_url(source, channel_url)
            if channel_payload.get("retcode") not in (0, "0"):
                raise RuntimeError(
                    f"官方來源回傳錯誤：{str(channel_payload.get('message') or '未知錯誤')[:200]}"
                )
            data = channel_payload.get("data")
            rows = data.get("list") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise RuntimeError("官方來源缺少公告分類清單。")
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                source_key = str(raw.get("iInfoId") or "").strip()
                if not source_key or source_key in seen_keys:
                    continue
                combined.append(raw)
                seen_keys.add(source_key)
        return {"retcode": 0, "message": "OK", "data": {"list": combined}}
    payload = _fetch_json_url(source, source.fetch_url)
    if source.parser != "kuro_static_json":
        return payload
    rows = payload.get("article")
    if not isinstance(rows, list):
        raise RuntimeError("鳴潮官方來源缺少公告清單。")
    base_url = source.fetch_url.rsplit("/MainMenu.json", 1)[0]
    details: dict[str, dict[str, Any]] = {}
    ordered_rows = sorted(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: str(row.get("startTime") or ""),
        reverse=True,
    )
    unique_rows: list[dict[str, Any]] = []
    seen_article_ids: set[str] = set()
    for row in ordered_rows:
        source_key = str(row.get("articleId") or "").strip()
        if not source_key or source_key in seen_article_ids:
            continue
        unique_rows.append(row)
        seen_article_ids.add(source_key)
    for row in unique_rows[:60]:
        source_key = str(row.get("articleId") or "").strip()
        try:
            details[source_key] = _fetch_json_url(
                source,
                f"{base_url}/article/{urllib.parse.quote(source_key, safe='')}.json",
            )
        except RuntimeError:
            continue
    if not details:
        raise RuntimeError("鳴潮官方來源沒有可讀取的近期活動公告；已保留既有資料。")
    payload["__details"] = details
    return payload


def _plain_text(value: Any) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(str(value or ""))
    except Exception:
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _parse_official_datetime(value: Any) -> int | None:
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M"):
        try:
            local = datetime.strptime(text, pattern).replace(tzinfo=_taipei_zone())
        except ValueError:
            continue
        return int(local.astimezone(UTC).timestamp())
    return None


DATE_TIME_PATTERN = re.compile(
    r"(?:(?P<year>20\d{2})\s*(?:年|[./-])\s*)?(?P<month>0?[1-9]|1[0-2])\s*"
    r"(?:月|[./-])\s*(?P<day>0?[1-9]|[12]\d|3[01])\s*(?:日)?\s*"
    r"(?P<hour>[01]?\d|2[0-3])\s*[:：]\s*(?P<minute>[0-5]\d)"
)


EVENT_TIME_LABEL_PATTERN = re.compile(
    r"(?:活動|祈願|躍遷|頻道|調頻|喚取|挑戰|賽事|申領|領取|開放|維護|更新)"
    r"(?:開放)?(?:時間|期間)|(?:開始|結束|截止)時間"
)
RANGE_CONNECTOR_PATTERN = re.compile(r"(?:至|到|~|～|—|–|-)")


def _matched_datetimes(text: str, published_at: int) -> list[tuple[int, int, int]]:
    values: list[tuple[int, int, int]] = []
    zone = _taipei_zone()
    publication = datetime.fromtimestamp(published_at, UTC).astimezone(zone)
    previous: datetime | None = None
    for match in DATE_TIME_PATTERN.finditer(text):
        try:
            parsed = datetime(
                int(match.group("year") or publication.year),
                int(match.group("month")),
                int(match.group("day")),
                int(match.group("hour")),
                int(match.group("minute")),
                tzinfo=zone,
            )
        except ValueError:
            continue
        if not match.group("year") and previous is not None and parsed < previous:
            try:
                parsed = parsed.replace(year=parsed.year + 1)
            except ValueError:
                continue
        if publication.year - 1 <= parsed.year <= publication.year + 2:
            values.append((int(parsed.astimezone(UTC).timestamp()), match.start(), match.end()))
            previous = parsed
    return values


def _window_from_segment(segment: str, published_at: int) -> tuple[int | None, int | None]:
    values = _matched_datetimes(segment, published_at)
    if not values:
        return None, None
    first_value, _, first_end_offset = values[0]
    shorthand_end = re.match(
        r"\s*(?:至|到|~|～|—|–|-)\s*(?P<hour>[01]?\d|2[0-3])\s*[:：]\s*(?P<minute>[0-5]\d)",
        segment[first_end_offset:],
    )
    if shorthand_end:
        zone = _taipei_zone()
        start_local = datetime.fromtimestamp(first_value, UTC).astimezone(zone)
        end_local = start_local.replace(
            hour=int(shorthand_end.group("hour")),
            minute=int(shorthand_end.group("minute")),
            second=0,
            microsecond=0,
        )
        if end_local <= start_local:
            end_local += timedelta(days=1)
        return first_value, int(end_local.astimezone(UTC).timestamp())
    if len(values) == 1:
        only, start_offset, end_offset = values[0]
        duration_match = re.search(r"預計\s*([1-9]|1\d|2[0-4])\s*個?小時", segment)
        if "維護" in segment and duration_match:
            return only, only + int(duration_match.group(1)) * 3600
        before = segment[max(0, start_offset - 18):start_offset].rstrip()
        after = segment[end_offset:min(len(segment), end_offset + 18)].lstrip()
        if re.search(r"(?:截止|結束|至|到|~|～|—|–|-)$", before) or re.search(
            r"^(?:截止|結束)", after
        ):
            return None, only
        if re.search(r"(?:開始|開放|自|從)$", before) or re.search(
            r"^(?:開始|起|開放)", after
        ):
            return only, None
        return None, None
    first, _, first_end = values[0]
    second, second_start, _ = values[1]
    connector = segment[first_end:second_start]
    if not RANGE_CONNECTOR_PATTERN.search(connector):
        return None, None
    if second <= first:
        return None, None
    return first, second


def _event_window(text: str, published_at: int) -> tuple[int | None, int | None]:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    duration_match = re.search(r"預計\s*([1-9]|1\d|2[0-4])\s*個?小時", normalized)
    if "維護" in normalized and duration_match:
        nearby_dates = [
            match for match in DATE_TIME_PATTERN.finditer(normalized)
            if 0 <= duration_match.start() - match.end() <= 120
        ]
        if nearby_dates:
            date_match = nearby_dates[-1]
            values = _matched_datetimes(
                normalized[date_match.start():duration_match.end()], published_at
            )
            if values:
                start_at = values[0][0]
                return start_at, start_at + int(duration_match.group(1)) * 3600
    labels = list(EVENT_TIME_LABEL_PATTERN.finditer(normalized))
    for index, label in enumerate(labels):
        next_offset = labels[index + 1].start() if index + 1 < len(labels) else len(normalized)
        segment = normalized[label.start():min(next_offset, label.start() + 360)]
        window = _window_from_segment(segment, published_at)
        if window != (None, None):
            return window
    values = _matched_datetimes(normalized, published_at)
    if len(values) >= 2:
        first_start = values[0][1]
        second_end = values[1][2]
        if second_end - first_start <= 180:
            return _window_from_segment(normalized[first_start:second_end], published_at)
    return None, None


INCLUDE_TITLE_KEYWORDS = (
    "活動",
    "祈願",
    "躍遷",
    "限時頻道",
    "喚取",
    "版本資訊",
    "更新維護",
    "停服維護",
    "維護公告",
    "版本更新",
    "簽到",
    "挑戰",
    "賽事",
    "召集",
    "兌換碼",
    "贈禮",
    "回歸",
    "紀行",
    "特許尋訪",
    "特賣",
    "協議邀約",
    "申領",
)
EXCLUDE_TITLE_KEYWORDS = (
    "角色展示",
    "過場動畫",
    "角色PV",
    "角色逸聞",
    "角色介紹",
    "戰鬥演示",
    "原聲帶",
    "音樂",
    "桌布",
    "桌面",
    "表情包",
    "聲優",
    "幕後",
)
CONTAINER_TITLE_KEYWORDS = (
    "版本更新說明",
    "版本內容說明",
    "版本資訊",
)


def _is_relevant_title(title: str) -> bool:
    return any(keyword in title for keyword in INCLUDE_TITLE_KEYWORDS) and not any(
        keyword in title for keyword in EXCLUDE_TITLE_KEYWORDS
    )


def _is_container_announcement(title: str) -> bool:
    return "維護" not in title and any(keyword in title for keyword in CONTAINER_TITLE_KEYWORDS)


def _is_hoyoverse_activity_notice(
    source: OfficialSource, raw: dict[str, Any], title: str
) -> bool:
    if _is_relevant_title(title):
        return True
    if any(keyword in title for keyword in EXCLUDE_TITLE_KEYWORDS):
        return False
    event_channels = HOYOVERSE_EVENT_CHANNEL_IDS.get(source.game_id, frozenset())
    raw_channels = {str(value) for value in (raw.get("sChanId") or [])}
    return bool(event_channels & raw_channels)


def _category_for_title(title: str) -> str:
    if "喚取" in title:
        return "活動喚取"
    if "頻道" in title:
        return "限時調頻"
    if "祈願" in title or "躍遷" in title:
        return "卡池與躍遷"
    if "維護" in title or "版本更新" in title:
        return "版本與維護"
    if "兌換碼" in title or "贈禮" in title:
        return "獎勵與兌換"
    return "限時活動"


def _banner_url(value: Any) -> str:
    try:
        payload = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    banners = payload.get("banner") if isinstance(payload, dict) else None
    if not isinstance(banners, list) or not banners or not isinstance(banners[0], dict):
        return ""
    candidate = str(banners[0].get("url") or "").strip()
    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme != "https" or not (parsed.hostname or "").lower().endswith("hoyoverse.com"):
        return ""
    return candidate[:1000]


def _html_paragraphs(value: Any) -> list[str]:
    paragraphs: list[str] = []
    for match in re.finditer(r"<p\b[^>]*>(?P<content>.*?)</p>", str(value or ""), re.IGNORECASE | re.DOTALL):
        text = TRADITIONAL_CONVERTER.convert(_plain_text(match.group("content")))
        if text:
            paragraphs.append(text)
    return paragraphs


def _hoyoverse_embedded_events(
    source: OfficialSource,
    raw: dict[str, Any],
    *,
    parent_source_key: str,
    parent_title: str,
    published_at: int,
) -> list[dict[str, Any]]:
    paragraphs = _html_paragraphs(raw.get("sContent"))
    section_start = next(
        (index for index, text in enumerate(paragraphs) if re.match(r"6[.、]\s*全新活動", text)),
        None,
    )
    if section_start is None:
        return []
    section_end = next(
        (
            index
            for index in range(section_start + 1, len(paragraphs))
            if re.match(r"7[.、]\s*其他內容", paragraphs[index])
        ),
        len(paragraphs),
    )
    events: list[dict[str, Any]] = []
    embedded_title = ""
    for paragraph in paragraphs[section_start + 1:section_end]:
        if paragraph.startswith("■"):
            embedded_title = paragraph.lstrip("■ ").strip()
            continue
        if not embedded_title or not re.match(r"活動時間\s*[:：]", paragraph):
            continue
        start_at, end_at = _event_window(paragraph, published_at)
        if end_at is None:
            continue
        embedded_key = (
            f"{parent_source_key}#activity-"
            f"{event_content_hash({'title': embedded_title})[:16]}"
        )
        event = {
            "source_key": embedded_key,
            "title": embedded_title[:300],
            "summary": f"收錄於「{parent_title}」官方公告。"[:1000],
            "category": _category_for_title(embedded_title),
            "start_at": start_at,
            "end_at": end_at,
            "official_url": source.detail_url_template.format(
                source_key=urllib.parse.quote(parent_source_key, safe="")
            ),
            "image_url": _banner_url(raw.get("sExt")),
            "language": "zh-TW",
            "source_updated_at": published_at,
        }
        event["content_hash"] = event_content_hash(event)
        events.append(event)
    return events


def parse_hoyoverse_content_v2(source: OfficialSource, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("retcode") not in (0, "0"):
        raise RuntimeError(f"官方來源回傳錯誤：{str(payload.get('message') or '未知錯誤')[:200]}")
    data = payload.get("data")
    rows = data.get("list") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("官方來源缺少活動清單。")
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        source_key = str(raw.get("iInfoId") or "").strip()
        title = TRADITIONAL_CONVERTER.convert(re.sub(r"\s+", " ", str(raw.get("sTitle") or "")).strip())
        if not source_key or not title or source_key in seen:
            continue
        if not _is_relevant_title(title):
            continue
        published_at = _parse_official_datetime(raw.get("dtCreateTime")) or _parse_official_datetime(raw.get("dtStartTime"))
        if published_at is None:
            continue
        full_text = TRADITIONAL_CONVERTER.convert(_plain_text(raw.get("sContent")))
        if _is_container_announcement(title):
            events.extend(
                _hoyoverse_embedded_events(
                    source,
                    raw,
                    parent_source_key=source_key,
                    parent_title=title,
                    published_at=published_at,
                )
            )
            seen.add(source_key)
            continue
        start_at, end_at = _event_window(f"{title} {full_text}", published_at)
        if end_at is None:
            continue
        summary = TRADITIONAL_CONVERTER.convert(re.sub(r"\s+", " ", str(raw.get("sIntro") or "")).strip())
        official_url = source.detail_url_template.format(
            source_key=urllib.parse.quote(source_key, safe="")
        )
        event = {
            "source_key": source_key,
            "title": title[:300],
            "summary": summary[:1000],
            "category": _category_for_title(title),
            "start_at": start_at,
            "end_at": end_at,
            "official_url": official_url,
            "image_url": _banner_url(raw.get("sExt")),
            "language": "zh-TW",
            "source_updated_at": published_at,
        }
        event["content_hash"] = event_content_hash(event)
        events.append(event)
        seen.add(source_key)
    events.sort(key=lambda row: (row.get("start_at") or row.get("source_updated_at") or 0, row["source_key"]))
    return events


def _kuro_image_url(content: str, source: OfficialSource) -> str:
    match = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", str(content or ""), re.IGNORECASE)
    if not match:
        return ""
    candidate = html.unescape(match.group(1)).strip()
    try:
        _validated_url(candidate, source)
    except ValueError:
        return ""
    return candidate[:1000]


def parse_kuro_static_json(source: OfficialSource, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("article")
    details = payload.get("__details")
    if not isinstance(rows, list) or not isinstance(details, dict):
        raise RuntimeError("鳴潮官方來源資料格式不正確。")
    rows_by_id = {
        str(row.get("articleId") or ""): row
        for row in rows
        if isinstance(row, dict) and row.get("articleId") not in (None, "")
    }
    events: list[dict[str, Any]] = []
    for source_key, detail in details.items():
        if not isinstance(detail, dict):
            continue
        row = rows_by_id.get(str(source_key), {})
        title = TRADITIONAL_CONVERTER.convert(
            re.sub(r"\s+", " ", str(detail.get("articleTitle") or row.get("articleTitle") or "")).strip()
        )
        if not title or not _is_relevant_title(title):
            continue
        if _is_container_announcement(title):
            continue
        published_at = _parse_official_datetime(detail.get("startTime") or row.get("startTime"))
        if published_at is None:
            continue
        raw_content = str(detail.get("articleContent") or "")
        full_text = TRADITIONAL_CONVERTER.convert(_plain_text(raw_content))
        start_at, end_at = _event_window(f"{title} {full_text}", published_at)
        if end_at is None:
            continue
        event = {
            "source_key": str(source_key),
            "title": title[:300],
            "summary": "",
            "category": _category_for_title(title),
            "start_at": start_at,
            "end_at": end_at,
            "official_url": source.detail_url_template.format(
                source_key=urllib.parse.quote(str(source_key), safe="")
            ),
            "image_url": _kuro_image_url(raw_content, source),
            "language": "zh-TW",
            "source_updated_at": published_at,
        }
        event["content_hash"] = event_content_hash(event)
        events.append(event)
    events.sort(key=lambda row: (row.get("start_at") or row.get("source_updated_at") or 0, row["source_key"]))
    return events


def parse_iwplay_html(source: OfficialSource, payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("entries")
    details = payload.get("__details")
    if not isinstance(entries, list) or not isinstance(details, dict):
        raise RuntimeError("異環官方來源資料格式不正確。")
    events: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_key = str(entry.get("source_key") or "").strip()
        title = TRADITIONAL_CONVERTER.convert(str(entry.get("title") or "").strip())
        detail_html = details.get(source_key)
        if not source_key or not title or not isinstance(detail_html, str) or not _is_relevant_title(title):
            continue
        if _is_container_announcement(title):
            continue
        date_match = re.match(r"(?P<date>20\d{6})/", source_key)
        if not date_match:
            continue
        try:
            publication = datetime.strptime(date_match.group("date"), "%Y%m%d").replace(tzinfo=_taipei_zone())
        except ValueError:
            continue
        published_at = int(publication.astimezone(UTC).timestamp())
        full_text = TRADITIONAL_CONVERTER.convert(_plain_text(detail_html))
        start_at, end_at = _event_window(f"{title} {full_text}", published_at)
        if "已維護完畢" in title and start_at is not None:
            actual_values = _matched_datetimes(title, published_at)
            if actual_values and actual_values[-1][0] > start_at:
                end_at = actual_values[-1][0]
        if end_at is None:
            continue
        event = {
            "source_key": source_key,
            "title": title[:300],
            "summary": "",
            "category": _category_for_title(title),
            "start_at": start_at,
            "end_at": end_at,
            "official_url": str(entry.get("official_url") or source.official_url)[:1000],
            "image_url": "",
            "language": "zh-TW",
            "source_updated_at": published_at,
        }
        event["content_hash"] = event_content_hash(event)
        events.append(event)
        embedded_match = re.search(
            r"六[、.]\s*全新活動(?P<section>.*?)(?:七[、.]\s*其他內容|$)",
            full_text,
            re.DOTALL,
        )
        if embedded_match:
            embedded_pattern = re.compile(
                r"●\s*「(?P<name>[^」]{2,100})」(?P<kind>[^●]{0,40}?)"
                r"活動時間\s*[:：]\s*(?P<window>.*?)(?=活動說明\s*[:：]|●|$)",
                re.DOTALL,
            )
            for embedded in embedded_pattern.finditer(embedded_match.group("section")):
                embedded_title = re.sub(
                    r"\s+", " ", f"「{embedded.group('name')}」{embedded.group('kind')}"
                ).strip()
                embedded_start, embedded_end = _event_window(
                    f"活動時間：{embedded.group('window')}", published_at
                )
                if embedded_end is None:
                    continue
                embedded_key = (
                    f"{source_key}#activity-"
                    f"{event_content_hash({'title': embedded_title})[:16]}"
                )
                embedded_event = {
                    "source_key": embedded_key,
                    "title": embedded_title[:300],
                    "summary": f"收錄於「{title}」官方公告。"[:1000],
                    "category": "限時活動",
                    "start_at": embedded_start,
                    "end_at": embedded_end,
                    "official_url": str(entry.get("official_url") or source.official_url)[:1000],
                    "image_url": "",
                    "language": "zh-TW",
                    "source_updated_at": published_at,
                }
                embedded_event["content_hash"] = event_content_hash(embedded_event)
                events.append(embedded_event)
    events.sort(key=lambda row: (row.get("start_at") or row.get("source_updated_at") or 0, row["source_key"]))
    return events


def parse_gryphline_next_html(source: OfficialSource, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("bulletins")
    details = payload.get("__details")
    if not isinstance(rows, list) or not isinstance(details, dict):
        raise RuntimeError("終末地官方來源資料格式不正確。")
    rows_by_id = {
        str(row.get("cid") or ""): row
        for row in rows
        if isinstance(row, dict) and row.get("cid") not in (None, "")
    }
    events: list[dict[str, Any]] = []
    for source_key, detail in details.items():
        raw_content = detail.get("data") if isinstance(detail, dict) else detail
        if not isinstance(raw_content, str):
            continue
        row = rows_by_id.get(str(source_key), {})
        title = TRADITIONAL_CONVERTER.convert(
            re.sub(r"\s+", " ", str(row.get("title") or "")).strip()
        )
        if not title or not _is_relevant_title(title):
            continue
        if _is_container_announcement(title):
            continue
        try:
            published_at = int(row.get("displayTime") or 0)
        except (TypeError, ValueError):
            continue
        if published_at <= 0:
            continue
        full_text = TRADITIONAL_CONVERTER.convert(_plain_text(raw_content))
        start_at, end_at = _event_window(f"{title} {full_text}", published_at)
        if end_at is None:
            continue
        cover = str(row.get("cover") or "").strip()
        cover_parts = urllib.parse.urlsplit(cover)
        if cover_parts.scheme != "https" or not (cover_parts.hostname or "").lower().endswith("hg-cdn.com"):
            cover = ""
        event = {
            "source_key": str(source_key),
            "title": title[:300],
            "summary": TRADITIONAL_CONVERTER.convert(
                re.sub(r"\s+", " ", str(row.get("brief") or "")).strip()
            )[:1000],
            "category": _category_for_title(title),
            "start_at": start_at,
            "end_at": end_at,
            "official_url": source.detail_url_template.format(
                source_key=urllib.parse.quote(str(source_key), safe="")
            ),
            "image_url": cover[:1000],
            "language": "zh-TW",
            "source_updated_at": published_at,
        }
        event["content_hash"] = event_content_hash(event)
        events.append(event)
    events.sort(key=lambda row: (row.get("start_at") or row.get("source_updated_at") or 0, row["source_key"]))
    return events


def parse_official_payload(source: OfficialSource, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if source.parser == "hoyoverse_content_v2":
        return parse_hoyoverse_content_v2(source, payload)
    if source.parser == "kuro_static_json":
        return parse_kuro_static_json(source, payload)
    if source.parser == "iwplay_html":
        return parse_iwplay_html(source, payload)
    if source.parser == "gryphline_next_html":
        return parse_gryphline_next_html(source, payload)
    raise RuntimeError("官方活動來源解析器尚未支援。")


def _candidate_raw_json(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(serialized) <= 200_000:
        return serialized
    return json.dumps(
        {
            "truncated": True,
            "content_hash": event_content_hash(value),
            "excerpt": serialized[:190_000],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _candidate_reason(*, published_at: int | None, text: str) -> str:
    if published_at is None:
        return "官方公告發布時間無法辨識"
    if not DATE_TIME_PATTERN.search(text):
        return "官方公告沒有提供可安全辨識的完整活動時間"
    return "官方公告的活動時間不完整或無法安全配對"


def _official_parse_candidates(
    source: OfficialSource,
    payload: dict[str, Any],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parsed_keys = {str(event.get("source_key") or "") for event in events}
    candidates: list[dict[str, Any]] = []
    if source.parser == "hoyoverse_content_v2":
        data = payload.get("data")
        rows = data.get("list") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return candidates
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            source_key = str(raw.get("iInfoId") or "").strip()
            title = TRADITIONAL_CONVERTER.convert(
                re.sub(r"\s+", " ", str(raw.get("sTitle") or "")).strip()
            )
            if (
                not source_key
                or source_key in parsed_keys
                or not _is_hoyoverse_activity_notice(source, raw, title)
            ):
                continue
            published_at = _parse_official_datetime(raw.get("dtCreateTime")) or _parse_official_datetime(
                raw.get("dtStartTime")
            )
            full_text = TRADITIONAL_CONVERTER.convert(_plain_text(raw.get("sContent")))
            candidates.append(
                {
                    "source_key": source_key,
                    "title": title[:300],
                    "official_url": source.detail_url_template.format(
                        source_key=urllib.parse.quote(source_key, safe="")
                    ),
                    "source_published_at": published_at,
                    "reason": _candidate_reason(published_at=published_at, text=full_text),
                    "raw_json": _candidate_raw_json({"announcement": raw}),
                }
            )
    elif source.parser == "kuro_static_json":
        rows = payload.get("article")
        details = payload.get("__details")
        if not isinstance(rows, list) or not isinstance(details, dict):
            return candidates
        rows_by_id = {
            str(row.get("articleId") or ""): row
            for row in rows
            if isinstance(row, dict) and row.get("articleId") not in (None, "")
        }
        for source_key, detail in details.items():
            if not isinstance(detail, dict) or str(source_key) in parsed_keys:
                continue
            row = rows_by_id.get(str(source_key), {})
            title = TRADITIONAL_CONVERTER.convert(
                re.sub(
                    r"\s+", " ", str(detail.get("articleTitle") or row.get("articleTitle") or "")
                ).strip()
            )
            full_text = TRADITIONAL_CONVERTER.convert(_plain_text(detail.get("articleContent")))
            if not _is_relevant_title(title) and not EVENT_TIME_LABEL_PATTERN.search(full_text):
                continue
            published_at = _parse_official_datetime(detail.get("startTime") or row.get("startTime"))
            candidates.append(
                {
                    "source_key": str(source_key),
                    "title": title[:300],
                    "official_url": source.detail_url_template.format(
                        source_key=urllib.parse.quote(str(source_key), safe="")
                    ),
                    "source_published_at": published_at,
                    "reason": _candidate_reason(published_at=published_at, text=full_text),
                    "raw_json": _candidate_raw_json({"listing": row, "announcement": detail}),
                }
            )
    elif source.parser == "iwplay_html":
        entries = payload.get("entries")
        details = payload.get("__details")
        if not isinstance(entries, list) or not isinstance(details, dict):
            return candidates
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            source_key = str(entry.get("source_key") or "").strip()
            detail_html = details.get(source_key)
            if not source_key or source_key in parsed_keys or not isinstance(detail_html, str):
                continue
            title = TRADITIONAL_CONVERTER.convert(str(entry.get("title") or "").strip())
            full_text = TRADITIONAL_CONVERTER.convert(_plain_text(detail_html))
            if (
                str(entry.get("source_category") or "") != "activity"
                and not _is_relevant_title(title)
                and not EVENT_TIME_LABEL_PATTERN.search(full_text)
            ):
                continue
            date_match = re.match(r"(?P<date>20\d{6})/", source_key)
            published_at = None
            if date_match:
                try:
                    publication = datetime.strptime(date_match.group("date"), "%Y%m%d").replace(
                        tzinfo=_taipei_zone()
                    )
                    published_at = int(publication.astimezone(UTC).timestamp())
                except ValueError:
                    pass
            candidates.append(
                {
                    "source_key": source_key,
                    "title": title[:300],
                    "official_url": str(entry.get("official_url") or source.official_url)[:1000],
                    "source_published_at": published_at,
                    "reason": _candidate_reason(published_at=published_at, text=full_text),
                    "raw_json": _candidate_raw_json(
                        {"listing": entry, "announcement_html": detail_html}
                    ),
                }
            )
    elif source.parser == "gryphline_next_html":
        rows = payload.get("bulletins")
        details = payload.get("__details")
        if not isinstance(rows, list) or not isinstance(details, dict):
            return candidates
        rows_by_id = {
            str(row.get("cid") or ""): row
            for row in rows
            if isinstance(row, dict) and row.get("cid") not in (None, "")
        }
        for source_key, detail in details.items():
            if str(source_key) in parsed_keys:
                continue
            row = rows_by_id.get(str(source_key), {})
            raw_content = detail.get("data") if isinstance(detail, dict) else detail
            if not isinstance(raw_content, str):
                continue
            title = TRADITIONAL_CONVERTER.convert(str(row.get("title") or "").strip())
            full_text = TRADITIONAL_CONVERTER.convert(_plain_text(raw_content))
            if (
                str(row.get("tab") or "") != "events"
                and not _is_relevant_title(title)
                and not EVENT_TIME_LABEL_PATTERN.search(full_text)
            ):
                continue
            try:
                published_at = int(row.get("displayTime") or 0) or None
            except (TypeError, ValueError):
                published_at = None
            candidates.append(
                {
                    "source_key": str(source_key),
                    "title": title[:300],
                    "official_url": source.detail_url_template.format(
                        source_key=urllib.parse.quote(str(source_key), safe="")
                    ),
                    "source_published_at": published_at,
                    "reason": _candidate_reason(published_at=published_at, text=full_text),
                    "raw_json": _candidate_raw_json({"listing": row, "announcement": detail}),
                }
            )
    candidates.sort(key=lambda row: (row.get("source_published_at") or 0, row["source_key"]), reverse=True)
    return candidates


def parse_official_payload_result(source: OfficialSource, payload: dict[str, Any]) -> dict[str, Any]:
    events = parse_official_payload(source, payload)
    candidates = _official_parse_candidates(source, payload, events)
    reference_times = [
        int(value)
        for value in [
            *(event.get("source_updated_at") for event in events),
            *(candidate.get("source_published_at") for candidate in candidates),
        ]
        if value not in (None, "")
    ]
    if reference_times:
        cutoff = max(reference_times) - RECENT_CANDIDATE_WINDOW_SECONDS
        candidates = [
            candidate
            for candidate in candidates
            if candidate.get("source_published_at") is None
            or int(candidate["source_published_at"]) >= cutoff
        ]
    return {"events": events, "candidates": candidates}


def _upsert_source_candidates(
    db: sqlite3.Connection,
    source: OfficialSource,
    candidates: list[dict[str, Any]],
    stamp: int,
) -> None:
    for candidate in candidates:
        source_key = str(candidate.get("source_key") or "").strip()
        if not source_key:
            continue
        db.execute(
            """insert into activity_source_candidates(
            id,game_id,source_id,source_key,title,official_url,source_published_at,reason,
            raw_json,status,first_seen_at,last_seen_at)
            values(?,?,?,?,?,?,?,?,?,'pending',?,?)
            on conflict(game_id,source_id,source_key) do update set
            title=excluded.title,official_url=excluded.official_url,
            source_published_at=excluded.source_published_at,reason=excluded.reason,
            status=case when activity_source_candidates.raw_json<>excluded.raw_json then 'pending'
                else activity_source_candidates.status end,
            linked_event_id=case when activity_source_candidates.raw_json<>excluded.raw_json then null
                else activity_source_candidates.linked_event_id end,
            reviewed_by=case when activity_source_candidates.raw_json<>excluded.raw_json then null
                else activity_source_candidates.reviewed_by end,
            reviewed_at=case when activity_source_candidates.raw_json<>excluded.raw_json then null
                else activity_source_candidates.reviewed_at end,
            review_reason=case when activity_source_candidates.raw_json<>excluded.raw_json then ''
                else activity_source_candidates.review_reason end,
            raw_json=excluded.raw_json,last_seen_at=excluded.last_seen_at""",
            (
                f"{source.id}:candidate:{source_key}",
                source.game_id,
                source.id,
                source_key,
                str(candidate.get("title") or "")[:300],
                str(candidate.get("official_url") or "")[:1000],
                candidate.get("source_published_at"),
                str(candidate.get("reason") or "")[:1000],
                str(candidate.get("raw_json") or "{}"),
                stamp,
                stamp,
            ),
        )


def _existing_events(db: sqlite3.Connection, source_id: str) -> dict[str, dict[str, Any]]:
    rows = db.execute(
        """select id,game_id,source_id,source_key,title,summary,category,start_at,end_at,
        official_url,image_url,language,source_updated_at,content_hash,published,review_state,
        removed_at,created_at,updated_at
        from activity_events where source_id=? order by source_key""",
        (source_id,),
    ).fetchall()
    return {str(row["source_key"]): dict(row) for row in rows}


def _diff_events(current: dict[str, dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_by_key = {str(row["source_key"]): row for row in candidate}
    added = [row for key, row in candidate_by_key.items() if key not in current]
    updated = [
        row for key, row in candidate_by_key.items()
        if key in current and str(current[key].get("content_hash") or "") != str(row.get("content_hash") or "")
    ]
    removed = [row for key, row in current.items() if key not in candidate_by_key and row.get("removed_at") is None]
    return {
        "added": added,
        "updated": updated,
        "removed": removed,
        "conflicts": [],
        "summary": {
            "fetched": len(candidate),
            "added": len(added),
            "updated": len(updated),
            "removed": len(removed),
            "conflicts": 0,
        },
    }


def preview_official_sync(
    db: sqlite3.Connection,
    game_id: str,
    stamp: int,
    *,
    fetcher: Callable[[OfficialSource], dict[str, Any]] = fetch_official_json,
) -> dict[str, Any]:
    source = source_for_game(game_id)
    ensure_sources(db, stamp)
    run_id = str(uuid.uuid4())
    db.execute(
        """insert into activity_sync_runs(
        id,source_id,status,started_at,snapshot_json,diff_json,error_message)
        values(?,?,'running',?,'{}','{}','')""",
        (run_id, source.id, stamp),
    )
    db.execute(
        "update activity_sources set last_attempt_at=?,last_error='',updated_at=? where id=?",
        (stamp, stamp, source.id),
    )
    try:
        payload = fetcher(source)
        parsed = parse_official_payload_result(source, payload)
        candidate = parsed["events"]
        source_candidates = parsed["candidates"]
        if not candidate and not source_candidates:
            raise RuntimeError("官方來源沒有解析出可安全顯示的限時活動；已保留既有資料。")
        _upsert_source_candidates(db, source, source_candidates, stamp)
        current = _existing_events(db, source.id)
        diff = _diff_events(current, candidate)
        diff["candidates"] = source_candidates
        diff["summary"]["candidates"] = len(source_candidates)
        status = "needs_review" if diff["removed"] or diff["conflicts"] else "preview_ready"
        source_hash = event_content_hash(candidate)
        snapshot = {
            "before": list(current.values()),
            "candidate": candidate,
            "source_candidates": source_candidates,
            "source_hash": source_hash,
        }
        summary = diff["summary"]
        db.execute(
            """update activity_sync_runs set status=?,fetched_count=?,added_count=?,updated_count=?,
            removed_count=?,conflict_count=?,snapshot_json=?,diff_json=?,completed_at=? where id=?""",
            (
                status,
                summary["fetched"],
                summary["added"],
                summary["updated"],
                summary["removed"],
                summary["conflicts"],
                json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
                json.dumps(diff, ensure_ascii=False, separators=(",", ":")),
                stamp,
                run_id,
            ),
        )
        db.execute(
            """update activity_sources set last_success_at=?,last_error='',last_content_hash=?,updated_at=?
            where id=?""",
            (stamp, source_hash, stamp, source.id),
        )
        return {"run_id": run_id, "source": source, "status": status, "diff": diff, "candidate": candidate}
    except Exception as exc:
        message = str(exc)[:1000]
        db.execute(
            "update activity_sync_runs set status='failed',error_message=?,completed_at=? where id=?",
            (message, stamp, run_id),
        )
        db.execute(
            "update activity_sources set last_error=?,updated_at=? where id=?",
            (message, stamp, source.id),
        )
        # Persist source health even though the caller receives an exception.
        # Otherwise a context-managed SQLite transaction would roll the failure
        # record back together with the unsuccessful request.
        db.commit()
        raise


def apply_official_preview(
    db: sqlite3.Connection,
    run_id: str,
    stamp: int,
    *,
    actor_user_id: str | None,
    include_removals: bool = False,
) -> dict[str, Any]:
    run = db.execute("select * from activity_sync_runs where id=?", (run_id,)).fetchone()
    if run is None:
        raise LookupError("找不到官方活動同步預覽。")
    if str(run["status"]) not in {"preview_ready", "needs_review"}:
        raise ValueError("這份官方活動同步預覽目前不能套用。")
    snapshot = json.loads(str(run["snapshot_json"] or "{}"))
    diff = json.loads(str(run["diff_json"] or "{}"))
    candidate = snapshot.get("candidate") if isinstance(snapshot, dict) else None
    if not isinstance(candidate, list):
        raise ValueError("官方活動同步預覽內容不完整。")
    if diff.get("conflicts"):
        raise ValueError("官方活動同步存在衝突，必須先由管理員處理。")
    source_id = str(run["source_id"])
    source_row = db.execute("select game_id from activity_sources where id=?", (source_id,)).fetchone()
    if source_row is None:
        raise LookupError("找不到官方活動來源。")
    game_id = str(source_row["game_id"])
    for event in candidate:
        if not isinstance(event, dict):
            continue
        source_key = str(event.get("source_key") or "").strip()
        if not source_key:
            continue
        event_id = f"{source_id}:{source_key}"
        db.execute(
            """insert into activity_events(
            id,game_id,source_id,source_key,title,summary,category,start_at,end_at,official_url,
            image_url,language,source_updated_at,content_hash,published,review_state,removed_at,
            created_at,updated_at)
            values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,'approved',null,?,?)
            on conflict(id) do update set
            title=excluded.title,summary=excluded.summary,category=excluded.category,
            start_at=excluded.start_at,end_at=excluded.end_at,official_url=excluded.official_url,
            image_url=excluded.image_url,language='zh-TW',source_updated_at=excluded.source_updated_at,
            content_hash=excluded.content_hash,published=1,review_state='approved',removed_at=null,
            updated_at=excluded.updated_at""",
            (
                event_id,
                game_id,
                source_id,
                source_key,
                str(event.get("title") or "")[:300],
                str(event.get("summary") or "")[:1000],
                str(event.get("category") or "限時活動")[:80],
                event.get("start_at"),
                event.get("end_at"),
                str(event.get("official_url") or "")[:1000],
                str(event.get("image_url") or "")[:1000],
                "zh-TW",
                event.get("source_updated_at"),
                str(event.get("content_hash") or event_content_hash(event)),
                stamp,
                stamp,
            ),
        )
        db.execute(
            """update activity_source_candidates set status='linked',linked_event_id=?,
            reviewed_at=coalesce(reviewed_at,?),review_reason=case when review_reason=''
                then '官方來源後續提供完整活動時間，系統已自動連結。' else review_reason end
            where source_id=? and source_key=? and status='pending'""",
            (event_id, stamp, source_id, source_key),
        )
    if include_removals:
        candidate_keys = [str(row.get("source_key") or "") for row in candidate if isinstance(row, dict)]
        placeholders = ",".join("?" for _ in candidate_keys)
        if candidate_keys:
            db.execute(
                f"""update activity_events set published=0,review_state='approved',removed_at=?,updated_at=?
                where source_id=? and source_key not in ({placeholders}) and removed_at is null""",
                (stamp, stamp, source_id, *candidate_keys),
            )
        else:
            raise ValueError("空白候選清單不可移除既有活動。")
    needs_review = bool(diff.get("removed")) and not include_removals
    status = "needs_review" if needs_review else "applied"
    db.execute(
        "update activity_sync_runs set status=?,applied_at=?,applied_by=? where id=?",
        (status, stamp, actor_user_id, run_id),
    )
    return {
        "run_id": run_id,
        "status": status,
        "applied": len(candidate),
        "retained_for_review": len(diff.get("removed") or []) if needs_review else 0,
    }


def sync_official_game(
    db: sqlite3.Connection,
    game_id: str,
    stamp: int,
    *,
    actor_user_id: str | None = None,
    fetcher: Callable[[OfficialSource], dict[str, Any]] = fetch_official_json,
) -> dict[str, Any]:
    preview = preview_official_sync(db, game_id, stamp, fetcher=fetcher)
    if preview["diff"].get("conflicts"):
        return {"run_id": preview["run_id"], "status": "needs_review", "diff": preview["diff"]}
    applied = apply_official_preview(
        db,
        preview["run_id"],
        stamp,
        actor_user_id=actor_user_id,
        include_removals=False,
    )
    return {**applied, "diff": preview["diff"]}


def resolve_official_review(
    db: sqlite3.Connection,
    run_id: str,
    stamp: int,
    *,
    actor_user_id: str,
    action: str,
    reason: str,
) -> dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    normalized_reason = str(reason or "").strip()
    if normalized_action not in {"retain", "remove"}:
        raise ValueError("審核動作必須是保留或確認移除。")
    if len(normalized_reason) < 3:
        raise ValueError("請填寫至少 3 個字元的審核原因。")
    run = db.execute("select * from activity_sync_runs where id=?", (run_id,)).fetchone()
    if run is None:
        raise LookupError("找不到官方活動同步紀錄。")
    if str(run["status"]) != "needs_review":
        raise ValueError("這筆同步目前沒有待審核的疑似移除項目。")
    diff = json.loads(str(run["diff_json"] or "{}"))
    removed = diff.get("removed") if isinstance(diff, dict) else None
    if not isinstance(removed, list) or not removed:
        raise ValueError("這筆同步沒有可審核的疑似移除項目。")
    if normalized_action == "remove":
        result = apply_official_preview(
            db,
            run_id,
            stamp,
            actor_user_id=actor_user_id,
            include_removals=True,
        )
    else:
        result = {
            "run_id": run_id,
            "status": "applied",
            "applied": int(run["fetched_count"] or 0),
            "retained_for_review": len(removed),
        }
        db.execute(
            "update activity_sync_runs set status='applied',applied_at=coalesce(applied_at,?),applied_by=? where id=?",
            (stamp, actor_user_id, run_id),
        )
    diff["review_resolution"] = {
        "action": normalized_action,
        "reason": normalized_reason[:1000],
        "reviewed_at": stamp,
        "reviewed_by": actor_user_id,
    }
    db.execute(
        "update activity_sync_runs set diff_json=? where id=?",
        (json.dumps(diff, ensure_ascii=False, separators=(",", ":")), run_id),
    )
    return {**result, "review_action": normalized_action, "reviewed_count": len(removed)}


def rollback_official_run(
    db: sqlite3.Connection,
    run_id: str,
    stamp: int,
    *,
    actor_user_id: str,
    reason: str,
) -> dict[str, Any]:
    normalized_reason = str(reason or "").strip()
    if len(normalized_reason) < 3:
        raise ValueError("請填寫至少 3 個字元的回復原因。")
    run = db.execute("select * from activity_sync_runs where id=?", (run_id,)).fetchone()
    if run is None:
        raise LookupError("找不到官方活動同步紀錄。")
    if str(run["status"]) not in {"applied", "needs_review"}:
        raise ValueError("只有已套用且尚未回復的同步可以回復。")
    later = db.execute(
        """select id from activity_sync_runs where source_id=? and started_at>? and id<>?
        and status in ('applied','needs_review') order by started_at desc limit 1""",
        (run["source_id"], run["started_at"], run_id),
    ).fetchone()
    if later is not None:
        raise ValueError("此來源已有較新的同步；請從最新一筆開始回復。")
    try:
        snapshot = json.loads(str(run["snapshot_json"] or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("同步快照已損壞，無法安全回復。") from exc
    before = snapshot.get("before") if isinstance(snapshot, dict) else None
    if not isinstance(before, list) or any(not isinstance(row, dict) or not row.get("id") for row in before):
        raise ValueError("同步快照不完整，無法安全回復。")
    source_id = str(run["source_id"])
    before_ids = [str(row["id"]) for row in before]
    if before_ids:
        placeholders = ",".join("?" for _ in before_ids)
        db.execute(
            f"delete from activity_events where source_id=? and id not in ({placeholders})",
            (source_id, *before_ids),
        )
    else:
        db.execute("delete from activity_events where source_id=?", (source_id,))
    for event in before:
        db.execute(
            """insert into activity_events(
            id,game_id,source_id,source_key,title,summary,category,start_at,end_at,official_url,
            image_url,language,source_updated_at,content_hash,published,review_state,removed_at,
            created_at,updated_at)
            values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            on conflict(id) do update set
            game_id=excluded.game_id,source_id=excluded.source_id,source_key=excluded.source_key,
            title=excluded.title,summary=excluded.summary,category=excluded.category,
            start_at=excluded.start_at,end_at=excluded.end_at,official_url=excluded.official_url,
            image_url=excluded.image_url,language=excluded.language,
            source_updated_at=excluded.source_updated_at,content_hash=excluded.content_hash,
            published=excluded.published,review_state=excluded.review_state,
            removed_at=excluded.removed_at,created_at=excluded.created_at,updated_at=?""",
            (
                event["id"],
                event["game_id"],
                event.get("source_id"),
                event["source_key"],
                event["title"],
                event.get("summary", ""),
                event.get("category", "限時活動"),
                event.get("start_at"),
                event.get("end_at"),
                event.get("official_url", ""),
                event.get("image_url", ""),
                event.get("language", "zh-TW"),
                event.get("source_updated_at"),
                event["content_hash"],
                int(event.get("published", 0)),
                event.get("review_state", "pending"),
                event.get("removed_at"),
                int(event.get("created_at") or stamp),
                stamp,
                stamp,
            ),
        )
    diff = json.loads(str(run["diff_json"] or "{}"))
    diff["rollback"] = {
        "reason": normalized_reason[:1000],
        "rolled_back_at": stamp,
        "rolled_back_by": actor_user_id,
        "restored_count": len(before),
    }
    db.execute(
        "update activity_sync_runs set status='rolled_back',diff_json=? where id=?",
        (json.dumps(diff, ensure_ascii=False, separators=(",", ":")), run_id),
    )
    return {"run_id": run_id, "status": "rolled_back", "restored_count": len(before)}


def sync_run_history(db: sqlite3.Connection, limit: int = 30) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    rows = db.execute(
        """select r.*,s.game_id,s.name as source_name,g.name as game_name,g.display_order
        from activity_sync_runs r
        join activity_sources s on s.id=r.source_id
        join activity_games g on g.game_id=s.game_id
        order by r.started_at desc,g.display_order limit ?""",
        (safe_limit,),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        try:
            diff = json.loads(str(row["diff_json"] or "{}"))
        except json.JSONDecodeError:
            diff = {}
        removed = (diff.get("removed") if isinstance(diff, dict) else []) or []
        result.append(
            {
                "id": row["id"],
                "source_id": row["source_id"],
                "source_name": row["source_name"],
                "game_id": row["game_id"],
                "game_name": row["game_name"],
                "status": row["status"],
                "fetched_count": int(row["fetched_count"] or 0),
                "added_count": int(row["added_count"] or 0),
                "updated_count": int(row["updated_count"] or 0),
                "removed_count": int(row["removed_count"] or 0),
                "conflict_count": int(row["conflict_count"] or 0),
                "error_message": row["error_message"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "applied_at": row["applied_at"],
                "removed": [
                    {"source_key": item.get("source_key"), "title": item.get("title")}
                    for item in removed
                    if isinstance(item, dict)
                ],
                "review_resolution": diff.get("review_resolution") if isinstance(diff, dict) else None,
                "rollback": diff.get("rollback") if isinstance(diff, dict) else None,
            }
        )
    return result


def claim_scheduler_lease(
    db: sqlite3.Connection,
    *,
    owner_token: str,
    stamp: int,
    lease_seconds: int,
) -> bool:
    cursor = db.execute(
        """insert into activity_sync_leases(name,owner_token,expires_at,updated_at)
        values('activity-source-auto-sync',?,?,?)
        on conflict(name) do update set owner_token=excluded.owner_token,
        expires_at=excluded.expires_at,updated_at=excluded.updated_at
        where activity_sync_leases.expires_at<=excluded.updated_at
        or activity_sync_leases.owner_token=excluded.owner_token""",
        (owner_token, stamp + max(60, int(lease_seconds)), stamp),
    )
    return cursor.rowcount == 1


def release_scheduler_lease(db: sqlite3.Connection, *, owner_token: str, stamp: int) -> None:
    db.execute(
        """update activity_sync_leases set expires_at=0,updated_at=?
        where name='activity-source-auto-sync' and owner_token=?""",
        (stamp, owner_token),
    )


def source_health(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        """select s.*,g.name as game_name,g.display_order,
        (select count(*) from activity_events e where e.source_id=s.id and e.published=1 and e.removed_at is null) as event_count,
        (select status from activity_sync_runs r where r.source_id=s.id order by started_at desc limit 1) as latest_status
        from activity_sources s join activity_games g on g.game_id=s.game_id
        order by g.display_order,s.name"""
    ).fetchall()
    return [
        {
            "id": row["id"],
            "game_id": row["game_id"],
            "game_name": row["game_name"],
            "name": row["name"],
            "official_url": row["official_url"],
            "language": row["language"],
            "last_attempt_at": row["last_attempt_at"],
            "last_success_at": row["last_success_at"],
            "last_error": row["last_error"],
            "event_count": int(row["event_count"] or 0),
            "latest_status": row["latest_status"] or "尚未同步",
        }
        for row in rows
    ]
