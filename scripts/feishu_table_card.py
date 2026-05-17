#!/usr/bin/env python3
"""
feishu_table_card.py
Convert Markdown (tables + rich text) to Feishu messages.

Primary method: msg_type: post + tag: md (rich text post message).
Supports ALL markdown syntax: tables, bold, italic, code blocks, lists, etc.
Footer: agent and model info appended automatically.
Fallback: Schema 2.0 interactive card + tag: markdown, then plain text bullet list.
"""

import json
import os
import re
import sys

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://open.feishu.cn/open-apis"

DEFAULT_TIMEOUT = 15
MAX_ROWS = 200

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _load_config() -> dict:
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


_config = _load_config()


def _get_config(key: str, default=None):
    return _config.get(key, os.getenv(f"FEISHU_CARD_{key.upper()}", default))


def _get_app_id() -> str:
    return os.getenv("FEISHU_APP_ID", "")


def _get_app_secret() -> str:
    return os.getenv("FEISHU_APP_SECRET", "")


def _build_session() -> requests.Session:
    """Build a requests Session with retry and timeout defaults."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = _build_session()
    return _session


def get_tenant_token() -> str:
    app_id = _get_app_id()
    app_secret = _get_app_secret()
    if not app_id or not app_secret:
        raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET must be set")
    url = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
    r = _get_session().post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Token request failed: {data.get('msg', data)}")
    return data["tenant_access_token"]


def _is_separator_row(line: str) -> bool:
    """Return True if line is a Markdown table separator row (|---|---|---)."""
    cells = line.strip().strip("|").split("|")
    return all(re.match(r"^\s*[-:]+\s*$", cell) for cell in cells)


def parse_markdown_table(text: str, max_rows: int = MAX_ROWS) -> tuple[list[str], list[list[str]]]:
    """
    Parse a Markdown table from text.
    Returns (headers, rows). Truncates to max_rows if exceeded.
    Raises ValueError if no valid table is found.
    """
    lines = text.strip().splitlines()
    table_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if _is_separator_row(stripped):
                continue
            table_lines.append(stripped)

    if len(table_lines) < 2:
        raise ValueError(
            "No valid Markdown table found (need header + 1 data row). "
            "For non-table markdown content, use send_markdown_as_card() instead."
        )

    def parse_row(line):
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    headers = parse_row(table_lines[0])
    rows = [parse_row(line) for line in table_lines[1:]]

    if len(rows) > max_rows:
        rows = rows[:max_rows]

    return headers, rows


def _build_footer_text() -> str:
    agent = _get_config("footer_agent") or os.getenv("HERMES_AGENT_NAME", "")
    model = _get_config("footer_model") or os.getenv("HERMES_MODEL_NAME", "")
    parts = []
    if agent:
        parts.append(f"🤖 {agent}")
    if model:
        parts.append(f"Model: {model}")
    if not parts:
        return ""
    return "---\n" + " | ".join(parts)


def build_feishu_post(markdown_content: str) -> dict:
    """
    Build a Feishu post message payload with tag: md.
    No title. Footer with agent/model info if configured.
    """
    content_blocks = [[{"tag": "md", "text": markdown_content}]]
    footer_text = _build_footer_text()
    if footer_text:
        content_blocks.append([{"tag": "md", "text": footer_text}])
    return {
        "zh_cn": {
            "title": "",
            "content": content_blocks,
        }
    }


def send_markdown_as_post(chat_id: str, markdown_text: str) -> tuple[bool, str]:
    """
    Send markdown (text + table) as a Feishu post message with tag: md.
    No title. Footer with agent/model info if configured.
    Returns (success: bool, message: str).
    """
    post_content = build_feishu_post(markdown_text)
    token = get_tenant_token()
    result = _send_message(token, chat_id, "post", post_content)
    if result.get("code") == 0:
        return True, "Post message sent successfully!"
    else:
        return False, f"Failed: {result.get('msg', result.get('errmsg', 'unknown'))}"


# ─── Card-based rendering (legacy) ─────────────────────────────────────────

def build_feishu_card(markdown_content: str, title: str | None = None) -> dict:
    """
    Build a Feishu schema 2.0 card with full markdown content.
    Supports ALL markdown syntax: bold, italic, links, code, lists, tables, etc.
    If title is None and config has no card_title, header is omitted.
    """
    card: dict = {
        "schema": "2.0",
        "config": {"width_mode": "fill"},
    }
    effective_title = title if title is not None else _get_config("card_title")
    if effective_title:
        card["header"] = {
            "title": {"tag": "plain_text", "content": effective_title},
            "template": _get_config("header_template", "blue")
        }
    card["body"] = {
        "elements": [{
            "tag": "markdown",
            "content": markdown_content
        }]
    }
    return card


def _send_message(token: str, receive_id: str, msg_type: str, content: dict) -> dict:
    """Generic send message to a Feishu chat."""
    url = f"{BASE_URL}/im/v1/messages?receive_id_type=chat_id"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": json.dumps(content, ensure_ascii=False)
    }
    r = _get_session().post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    return r.json()


def send_card(token: str, receive_id: str, card: dict) -> dict:
    """Send a card message to a Feishu chat."""
    return _send_message(token, receive_id, "interactive", card)


def send_markdown_as_card(chat_id: str, markdown_text: str, title: str | None = None) -> tuple[bool, str]:
    """
    Send arbitrary markdown (text + table) as a Feishu card.
    Uses schema 2.0 + body.elements + tag:markdown, supports ALL markdown syntax.
    Returns (success: bool, message: str).
    """
    card = build_feishu_card(markdown_text, title=title)
    token = get_tenant_token()
    result = send_card(token, chat_id, card)
    if result.get("code") == 0:
        return True, "Markdown card sent successfully!"
    else:
        return False, f"Failed: {result.get('msg', result.get('errmsg', 'unknown'))}"


# ─── Plain-text bullet-list fallback ─────────────────────────────────────────

def table_to_bullet_list(headers: list[str], rows: list[list[str]], title: str = "",
                         title_emoji: str = "\U0001f4ca") -> str:
    """
    Convert a parsed table to a plain-text bullet list.
    Each row becomes a bullet point with all key:value pairs.
    """
    lines = []
    if title:
        lines.append(f"{title_emoji} {title}\n")
    for row in rows:
        parts = []
        for j in range(len(headers)):
            val = row[j] if j < len(row) else ""
            parts.append(f"{headers[j]}: {val}")
        lines.append("\u2022 " + "  |  ".join(parts))
    return "\n".join(lines)


def send_text_message(token: str, receive_id: str, text: str) -> dict:
    """Send a plain text message to a Feishu chat."""
    return _send_message(token, receive_id, "text", {"text": text})


def send_table_as_text_fallback(chat_id: str, markdown_text: str, title: str = "Data Table") -> tuple[bool, str]:
    """
    Convert a markdown table to a plain-text bullet list and send as text.
    Last resort fallback when card mode fails.
    Returns (success: bool, message: str).
    """
    headers, rows = parse_markdown_table(markdown_text)
    bullet_text = table_to_bullet_list(headers, rows, title)
    token = get_tenant_token()
    result = send_text_message(token, chat_id, bullet_text)
    if result.get("code") == 0:
        return True, f"Table sent as text (fallback). {len(rows)} rows delivered to Feishu."
    else:
        return False, f"Failed: {result.get('msg', result.get('errmsg', 'unknown'))}"


# ─── Fallback chain: post -> card -> text ────────────────────────────────────

def send_with_fallback(chat_id: str, markdown_text: str, title: str | None = None) -> str:
    """
    Try sending in order: post -> card -> text.
    Returns status message describing what succeeded or what final error occurred.
    """
    last_error = None

    # 1. Try post + tag:md mode (primary)
    try:
        success, msg = send_markdown_as_post(chat_id, markdown_text)
        if success:
            return msg
    except Exception as e:
        last_error = e

    # 2. Try card mode (legacy)
    try:
        success, msg = send_markdown_as_card(chat_id, markdown_text, title=title)
        if success:
            return msg
    except Exception as e:
        last_error = e

    # 3. Last resort: plain text bullet list
    try:
        success, msg = send_table_as_text_fallback(chat_id, markdown_text, title or "Data Table")
        if success:
            return msg
    except Exception as e:
        last_error = e

    return f"All send modes failed. Last error: {last_error}"


def send_table_with_fallback(chat_id: str, markdown_text: str, title: str = "Data Table") -> str:
    """
    Legacy fallback chain: card -> text.
    Returns status message describing what succeeded or what final error occurred.
    """
    last_error = None

    # 1. Try card mode (primary, supports ALL markdown syntax)
    try:
        success, msg = send_markdown_as_card(chat_id, markdown_text, title=title)
        if success:
            return msg
    except Exception as e:
        last_error = e

    # 2. Last resort: plain text bullet list
    try:
        success, msg = send_table_as_text_fallback(chat_id, markdown_text, title)
        if success:
            return msg
    except Exception as e:
        last_error = e

    return f"All send modes failed. Last error: {last_error}"


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Send Markdown (tables + rich text) to Feishu.")
    parser.add_argument("chat_id", nargs="?", help="Feishu chat ID")
    parser.add_argument("table_text", nargs="?", help="Markdown table/text (or read from stdin)")
    parser.add_argument("--post", action="store_true", default=True, help="Send as post+tag:md message (default)")
    parser.add_argument("--card", action="store_true", help="Send as interactive card (legacy)")
    parser.add_argument("--text", action="store_true", help="Send as plain text bullet list (fallback)")
    parser.add_argument("--fallback", action="store_true", default=True, help="Try post -> card -> text automatically (default)")
    parser.add_argument("--no-fallback", dest="fallback", action="store_false", help="Disable fallback, only try selected mode")
    parser.add_argument("--title", default=None, help="Card title (omit to hide header, only for --card mode)")
    args = parser.parse_args()

    if args.table_text:
        table_text = args.table_text
    else:
        table_text = sys.stdin.read().strip()

    if not args.chat_id:
        print("Usage: python feishu_table_card.py <chat_id> '<markdown>' [--post|--card|--text]")
        sys.exit(1)

    if args.text:
        _, result = send_table_as_text_fallback(args.chat_id, table_text, args.title)
    elif args.card:
        if args.fallback:
            result = send_table_with_fallback(args.chat_id, table_text, args.title)
        else:
            _, result = send_markdown_as_card(args.chat_id, table_text, args.title)
    else:
        if args.fallback:
            result = send_with_fallback(chat_id=args.chat_id, markdown_text=table_text, title=args.title)
        else:
            _, result = send_markdown_as_post(args.chat_id, table_text)
    print(result)