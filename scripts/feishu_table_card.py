#!/usr/bin/env python3
from __future__ import annotations
"""
feishu_table_card.py — Part of feishu-table-patch
Convert Markdown (tables + rich text) to Feishu messages.

Primary method: msg_type: post + tag: md (rich text post message).
Supports ALL markdown syntax: tables, bold, italic, code blocks, lists, etc.
Fallback: Schema 2.0 interactive card + tag: markdown, then plain text bullet list.
"""

import json
import os
import re
import sys
import threading

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
    val = _config.get(key)
    if val is not None:
        return val
    return os.getenv(f"FEISHU_CARD_{key.upper()}", default)


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


import threading

_session: requests.Session | None = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    with _session_lock:
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


def _extract_all_tables(text: str) -> list[tuple[str, str]]:
    """
    Extract all markdown tables from text, splitting into segments.
    Returns list of (segment_text, is_table) pairs.
    Non-table segments keep their original text; table segments
    contain just the table lines for parsing.
    """
    lines = text.splitlines()
    segments: list[tuple[str, str]] = []
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 2:
            if i + 1 < len(lines):
                sep = lines[i + 1].strip()
                if sep.startswith("|") and sep.endswith("|"):
                    cells = sep.strip("|").split("|")
                    if all(re.match(r"^\s*[-:]+\s*$", c) for c in cells):
                        j = i + 2
                        while j < len(lines):
                            s = lines[j].strip()
                            if s.startswith("|") and s.endswith("|"):
                                j += 1
                            else:
                                break
                        table_text = "\n".join(lines[i:j])
                        segments.append((table_text, "table"))
                        i = j
                        continue
        non_table_lines = []
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("|") and s.endswith("|") and len(s) > 2:
                if i + 1 < len(lines):
                    sep = lines[i + 1].strip()
                    if sep.startswith("|") and sep.endswith("|"):
                        cells = sep.strip("|").split("|")
                        if all(re.match(r"^\s*[-:]+\s*$", c) for c in cells):
                            break
            non_table_lines.append(lines[i])
            i += 1
        if non_table_lines:
            segments.append(("\n".join(non_table_lines).strip(), "text"))

    if not segments:
        return [(text, "text")]

    return segments


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
        cleaned = line.replace('\\\\', '\x00DBSLASH\x00')
        cleaned = re.sub(r'(?<!\\)\\|', '\x00PIPE\x00', cleaned)
        cells = [cell.strip().replace('\x00PIPE\x00', '|').replace('\x00DBSLASH\x00', '\\\\') for cell in cleaned.strip().strip("|").split("|")]
        return cells

    headers = parse_row(table_lines[0])
    rows = [parse_row(line) for line in table_lines[1:]]

    if len(rows) > max_rows:
        rows = rows[:max_rows]

    return headers, rows


def build_feishu_post(markdown_content: str) -> dict:
    """
    Build a Feishu post message payload with tag: md.
    No title, no footer.
    """
    return {
        "zh_cn": {
            "title": "",
            "content": [[{"tag": "md", "text": markdown_content}]],
        }
    }


def send_markdown_as_post(chat_id: str, markdown_text: str) -> tuple[bool, str]:
    """
    Send markdown (text + table) as a Feishu post message with tag: md.
    No title, no footer.
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
    Convert markdown tables to plain-text bullet lists and send as text.
    Preserves non-table content. Handles multiple tables.
    Last resort fallback when card mode fails.
    Returns (success: bool, message: str).
    """
    segments = _extract_all_tables(markdown_text)
    has_table = any(kind == "table" for _, kind in segments)
    if not has_table:
        full_text = markdown_text
    else:
        parts = []
        for seg_text, kind in segments:
            if kind == "table":
                try:
                    headers, rows = parse_markdown_table(seg_text)
                    bullet_text = table_to_bullet_list(headers, rows, title)
                    parts.append(bullet_text)
                except ValueError:
                    parts.append(seg_text)
            else:
                if seg_text:
                    parts.append(seg_text)
        full_text = "\n\n".join(parts)
    token = get_tenant_token()
    result = send_text_message(token, chat_id, full_text)
    if result.get("code") == 0:
        return True, f"Table sent as text (fallback). Delivered to Feishu."
    else:
        return False, f"Failed: {result.get('msg', result.get('errmsg', 'unknown'))}"


# ─── Fallback chain: post -> card -> text ────────────────────────────────────

def send_with_fallback(chat_id: str, markdown_text: str, title: str | None = None) -> str:
    """
    Try sending in order: post -> card -> text.
    Auth errors (missing credentials) fail fast without retrying.
    Returns status message describing what succeeded or what final error occurred.
    """
    last_error = None

    for sender in [send_markdown_as_post, send_markdown_as_card, send_table_as_text_fallback]:
        try:
            if sender == send_table_as_text_fallback:
                success, msg = sender(chat_id, markdown_text, title or "Data Table")
            elif sender == send_markdown_as_card:
                success, msg = sender(chat_id, markdown_text, title=title)
            else:
                success, msg = sender(chat_id, markdown_text)
            if success:
                return msg
        except ValueError as e:
            if "FEISHU_APP_ID" in str(e) or "FEISHU_APP_SECRET" in str(e):
                return f"Auth error: {e}"
            last_error = e
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
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--post", action="store_true", help="Send as post+tag:md message (default)")
    mode_group.add_argument("--card", action="store_true", help="Send as interactive card (legacy)")
    mode_group.add_argument("--text", action="store_true", help="Send as plain text bullet list (fallback)")
    parser.add_argument("--fallback", action="store_true", default=True, help="Try post -> card -> text automatically (default)")
    parser.add_argument("--no-fallback", dest="fallback", action="store_false", help="Disable fallback, only try selected mode")
    parser.add_argument("--title", default=None, help="Card title (omit to hide header, only for --card mode)")
    args = parser.parse_args()

    if args.table_text:
        table_text = args.table_text
    else:
        table_text = sys.stdin.read().strip()

    if not args.chat_id:
        print("Usage: python feishu_table_card.py <chat_id> '<markdown>' [--post|--card|--text]", file=sys.stderr)
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