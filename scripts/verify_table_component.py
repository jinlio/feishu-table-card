#!/usr/bin/env python3
"""
Verify Feishu native table component rendering and width support.

Sends 3 test messages to the same chat for side-by-side comparison:
  Test A: tag: table with verified format (no width)
  Test B: tag: table with width fields
  Test C: post + tag: md (current approach, control group)

Usage:
  python3 verify_table_component.py <chat_id>
"""

import json
import os
import sys
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://open.feishu.cn/open-apis"
DEFAULT_TIMEOUT = 15

_session: requests.Session | None = None
_session_lock = threading.Lock()


def _build_session() -> requests.Session:
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


def _get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            _session = _build_session()
        return _session


def get_tenant_token() -> str:
    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET must be set")
    url = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
    r = _get_session().post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Token request failed: {data.get('msg', data)}")
    return data["tenant_access_token"]


def _send_message(token: str, receive_id: str, msg_type: str, content: dict) -> dict:
    url = f"{BASE_URL}/im/v1/messages?receive_id_type=chat_id"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": json.dumps(content, ensure_ascii=False),
    }
    r = _get_session().post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    result = r.json()
    print(f"  API response: code={result.get('code')}, msg={result.get('msg', '')}", flush=True)
    return result


# ─── Test data ──────────────────────────────────────────────────────────────

SAMPLE_HEADERS = ["发现", "说明"]
SAMPLE_ROWS = [
    ["验证论文真实性这个需求已被验证", "CiteGuard 的 README 引用了 arXiv 2026 政策，明确表示需要外部工具来验证论文的真实性"],
    ["确定性验证 > LLM 验证", "两个最高匹配度的项目都选择了 API 为主的外部确定性验证，而非依赖 LLM 自身判断"],
    ["开源生态正在形成", "GitHub 上已有多个项目围绕论文验证、引用检查等方向构建工具链"],
]


# ─── Test A: tag: table (verified format, no width) ─────────────────────────

def build_card_table_no_width() -> dict:
    columns = [
        {"tag": "column", "name": {"tag": "plain_text", "content": h}}
        for h in SAMPLE_HEADERS
    ]
    return {
        "schema": "2.0",
        "config": {"width_mode": "fill"},
        "header": {
            "title": {"tag": "plain_text", "content": "Test A: tag:table (no width)"},
            "template": "blue",
        },
        "body": {
            "elements": [
                {"tag": "table", "columns": columns, "rows": SAMPLE_ROWS}
            ]
        },
    }


# ─── Test B: tag: table (with width) ────────────────────────────────────────

def build_card_table_with_width() -> dict:
    columns = [
        {
            "tag": "column",
            "name": {"tag": "plain_text", "content": SAMPLE_HEADERS[0]},
            "width": "35%",
        },
        {
            "tag": "column",
            "name": {"tag": "plain_text", "content": SAMPLE_HEADERS[1]},
            "width": "65%",
        },
    ]
    return {
        "schema": "2.0",
        "config": {"width_mode": "fill"},
        "header": {
            "title": {"tag": "plain_text", "content": "Test B: tag:table (width=35%/65%)"},
            "template": "blue",
        },
        "body": {
            "elements": [
                {"tag": "table", "columns": columns, "rows": SAMPLE_ROWS}
            ]
        },
    }


# ─── Test C: post + tag: md (control) ───────────────────────────────────────

def build_post_md() -> dict:
    lines = [
        "| 发现 | 说明 |",
        "|---|---|",
    ]
    for row in SAMPLE_ROWS:
        lines.append(f"| {row[0]} | {row[1]} |")
    md_text = "\n".join(lines)

    return {
        "zh_cn": {
            "title": "",
            "content": [
                [{"tag": "md", "text": f"**Test C: post + tag:md (current approach)**\n\n{md_text}"}]
            ],
        }
    }


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <chat_id>", file=sys.stderr)
        sys.exit(1)

    chat_id = sys.argv[1]
    token = get_tenant_token()
    print(f"Token obtained. Sending 3 test messages to chat_id={chat_id}...\n", flush=True)

    print("=== Test A: tag:table without width ===", flush=True)
    card_a = build_card_table_no_width()
    _send_message(token, chat_id, "interactive", card_a)

    print("\n=== Test B: tag:table with width (35%/65%) ===", flush=True)
    card_b = build_card_table_with_width()
    _send_message(token, chat_id, "interactive", card_b)

    print("\n=== Test C: post + tag:md (control) ===", flush=True)
    post_c = build_post_md()
    _send_message(token, chat_id, "post", post_c)

    print("\nDone. Check your Feishu client for results.", flush=True)


if __name__ == "__main__":
    main()
