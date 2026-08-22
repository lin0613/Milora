from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse


MAX_GUIDE_HTML_LENGTH = 250_000
MAX_GUIDE_PLAIN_TEXT_LENGTH = 80_000
GUIDE_IMAGE_PATH_PATTERN = re.compile(r"^/api/guide-media/[0-9a-fA-F-]{36}$")
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
BILIBILI_ID_PATTERN = re.compile(r"^BV[A-Za-z0-9]{8,20}$", re.IGNORECASE)
ALLOWED_FONT_SIZES = {"12px", "14px", "16px", "18px", "20px", "24px", "28px", "32px"}
ALLOWED_ALIGNMENTS = {"left", "center", "right"}
ALLOWED_TAGS = {
    "p", "br", "h2", "h3", "strong", "b", "em", "i", "u", "s", "strike", "del", "span",
    "ul", "ol", "li", "a", "blockquote", "figure", "figcaption", "img", "hr",
}
VOID_TAGS = {"br", "img", "hr"}


def normalize_external_link(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) > 2_000:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return raw


def normalize_video_url(value: str) -> str:
    raw = normalize_external_link(value)
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    path = parsed.path.strip("/")
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}:
        video_id = ""
        if path == "watch":
            video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        elif path.startswith("embed/") or path.startswith("shorts/"):
            video_id = path.split("/", 1)[1].split("/", 1)[0]
        if YOUTUBE_ID_PATTERN.fullmatch(video_id):
            return f"https://www.youtube.com/watch?v={video_id}"
    if host == "youtu.be":
        video_id = path.split("/", 1)[0]
        if YOUTUBE_ID_PATTERN.fullmatch(video_id):
            return f"https://www.youtube.com/watch?v={video_id}"
    if host in {"bilibili.com", "www.bilibili.com", "m.bilibili.com"}:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0].lower() == "video" and BILIBILI_ID_PATTERN.fullmatch(parts[1]):
            return f"https://www.bilibili.com/video/{parts[1]}"
    return ""


def video_embed_url(value: str) -> str:
    normalized = normalize_video_url(value)
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    if (parsed.hostname or "").lower().endswith("youtube.com"):
        video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        return f"https://www.youtube-nocookie.com/embed/{video_id}"
    match = re.search(r"/video/(BV[A-Za-z0-9]+)", parsed.path, re.IGNORECASE)
    if match:
        return f"https://player.bilibili.com/player.html?bvid={match.group(1)}&page=1"
    return ""


def _sanitize_style(tag: str, value: str) -> str:
    accepted: list[str] = []
    for declaration in str(value or "").split(";"):
        if ":" not in declaration:
            continue
        name, raw = declaration.split(":", 1)
        name = name.strip().lower()
        normalized = raw.strip().lower()
        if name == "color" and tag == "span" and HEX_COLOR_PATTERN.fullmatch(normalized):
            accepted.append(f"color:{normalized}")
        elif name == "font-size" and tag == "span" and normalized in ALLOWED_FONT_SIZES:
            accepted.append(f"font-size:{normalized}")
        elif name == "text-align" and tag in {"p", "h2", "h3", "blockquote"} and normalized in ALLOWED_ALIGNMENTS:
            accepted.append(f"text-align:{normalized}")
    return ";".join(accepted)


class GuideHTMLSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.open_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return
        raw_attrs = {str(name).lower(): str(value or "") for name, value in attrs}
        safe_attrs: list[tuple[str, str]] = []
        style = _sanitize_style(tag, raw_attrs.get("style", ""))
        if style:
            safe_attrs.append(("style", style))
        if tag == "span" and raw_attrs.get("class") == "guideSpoiler":
            safe_attrs.extend((("class", "guideSpoiler"), ("data-spoiler", "1"), ("tabindex", "0"), ("role", "button")))
        elif tag == "a":
            href = normalize_external_link(raw_attrs.get("href", ""))
            if href:
                safe_attrs.extend((("href", href), ("target", "_blank"), ("rel", "noopener noreferrer nofollow")))
        elif tag == "img":
            src = raw_attrs.get("src", "").strip()
            if not GUIDE_IMAGE_PATH_PATTERN.fullmatch(src):
                return
            safe_attrs.extend((("src", src), ("alt", raw_attrs.get("alt", "")[:300]), ("loading", "lazy"), ("decoding", "async")))
        elif tag == "figure":
            figure_class = raw_attrs.get("class", "")
            if figure_class == "guideImage":
                safe_attrs.append(("class", "guideImage"))
            elif figure_class == "guideVideo":
                video_url = normalize_video_url(raw_attrs.get("data-guide-video-url", ""))
                if not video_url:
                    return
                safe_attrs.extend((("class", "guideVideo"), ("data-guide-video-url", video_url)))
        rendered = "".join(f' {name}="{html.escape(value, quote=True)}"' for name, value in safe_attrs)
        self.output.append(f"<{tag}{rendered}>")
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag not in self.open_tags:
            return
        while self.open_tags:
            current = self.open_tags.pop()
            self.output.append(f"</{current}>")
            if current == tag:
                break

    def handle_data(self, data: str) -> None:
        self.output.append(html.escape(data, quote=False))

    def close_document(self) -> str:
        while self.open_tags:
            self.output.append(f"</{self.open_tags.pop()}>")
        return "".join(self.output).strip()


class GuideTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.parts.append(value)


def sanitize_guide_html(value: str) -> str:
    raw = str(value or "")
    if len(raw) > MAX_GUIDE_HTML_LENGTH:
        raise ValueError("攻略內容過長。")
    parser = GuideHTMLSanitizer()
    parser.feed(raw)
    parser.close()
    return parser.close_document()


def guide_plain_text(value: str) -> str:
    parser = GuideTextExtractor()
    parser.feed(str(value or ""))
    parser.close()
    return "\n".join(parser.parts)[:MAX_GUIDE_PLAIN_TEXT_LENGTH]


def guide_has_content(value: str) -> bool:
    sanitized = str(value or "")
    return bool(guide_plain_text(sanitized) or "<img " in sanitized or 'class="guideVideo"' in sanitized)
