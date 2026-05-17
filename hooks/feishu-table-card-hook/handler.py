import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.hermes/skills/productivity/feishu-table-card/scripts"))
from feishu_table_card import build_feishu_card, get_tenant_token

_MARKDOWN_TABLE_RE = re.compile(r"^\|.*\|\n\|[-|: ]+\|", re.MULTILINE)


def handle(event_type, context):
    content = context.get("content", "")
    if not _MARKDOWN_TABLE_RE.search(content):
        return None

    try:
        token = get_tenant_token()
        card = build_feishu_card(content)
        return {
            "msg_type": "interactive",
            "payload": json.dumps(card, ensure_ascii=False),
        }
    except Exception:
        return None