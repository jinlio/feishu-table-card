import os
import re
import subprocess
import sys

_MARKDOWN_TABLE_RE = re.compile(r"^\|.*\|\n\|[-|: ]+\|", re.MULTILINE)

_SCRIPT_DIR = os.path.join(
    os.path.expanduser("~"),
    ".hermes", "skills", "productivity", "feishu-table-card", "scripts",
)
_SCRIPT_PATH = os.path.join(_SCRIPT_DIR, "feishu_table_card.py")


def handle(event_type, context):
    content = context.get("content", "")
    if not _MARKDOWN_TABLE_RE.search(content):
        return None

    chat_id = context.get("chat_id", "")
    if not chat_id:
        return None

    try:
        result = subprocess.run(
            [sys.executable, _SCRIPT_PATH, "--post", "--no-fallback", chat_id],
            input=content,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "FEISHU_APP_ID": os.getenv("FEISHU_APP_ID", ""),
                 "FEISHU_APP_SECRET": os.getenv("FEISHU_APP_SECRET", "")},
        )
        if result.returncode == 0:
            return {"_consumed": True}
    except Exception:
        pass

    return None
