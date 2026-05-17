#!/usr/bin/env bash
# install.sh — Patch Hermes Agent's FeishuAdapter to send markdown tables as post+tag:md
# Usage: ./install.sh          (install patch)
#        ./install.sh --uninstall  (remove patch)
#        ./install.sh --check      (check if patch is applied)
#
# This script patches Hermes's _build_outbound_payload method so that when
# it detects a markdown table in outbound content, it sends it as a
# msg_type: post + tag: md message instead of plain text.
# The patch is idempotent and reversible.
# Compatible with Linux and macOS.

set -euo pipefail

# Portable Python command detection
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done
if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python is not installed. Please install Python 3 first."
    exit 1
fi

HERMES_DIR="${HERMES_DIR:-$($PYTHON_CMD -c "import importlib.util; spec=importlib.util.find_spec('gateway'); print(spec.origin.rsplit('/',1)[0]) if spec and spec.origin else ''" 2>/dev/null || true)}"

if [ -z "$HERMES_DIR" ]; then
    HERMES_DIR="$($PYTHON_CMD -c "
import site, glob, os
for sp in site.getsitepackages() + [site.getusersitepackages()]:
    p = os.path.join(sp, 'gateway')
    if os.path.isdir(p):
        print(sp)
        break
else:
    for pattern in [os.path.expanduser('~/.virtualenvs/*/lib/python3*/site-packages'),
                    '/opt/venvs/*/lib/python3*/site-packages',
                    '/usr/lib/python3/dist-packages',
                    '/usr/local/lib/python3*/dist-packages',
                    '/usr/lib64/python3*/site-packages']:
        for d in glob.glob(pattern):
            if os.path.isdir(os.path.join(d, 'gateway')):
                print(d)
                break
" 2>/dev/null || true)"
fi

if [ -z "$HERMES_DIR" ]; then
    echo "ERROR: Cannot find Hermes Agent installation directory."
    echo "Set HERMES_DIR environment variable to the site-packages path."
    exit 1
fi

FEISHU_PY="$HERMES_DIR/gateway/platforms/feishu.py"

MARKER="# [FEISHU-TABLE-CARD-PATCH]"

action="${1:-install}"

check_patch() {
    if grep -qF "$MARKER" "$FEISHU_PY" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

backup_file() {
    local f="$1"
    if [ ! -f "${f}.bak" ]; then
        cp "$f" "${f}.bak"
        echo "Backed up $f → ${f}.bak"
    fi
}

install_patch() {
    if check_patch; then
        echo "Patch already applied. Skipping."
        return 0
    fi

    if [ ! -f "$FEISHU_PY" ]; then
        echo "ERROR: $FEISHU_PY not found."
        exit 1
    fi

    backup_file "$FEISHU_PY"

    # Patch: Insert a helper method and modify _build_outbound_payload
    # to detect markdown tables and send as post+tag:md instead of plain text
    $PYTHON_CMD - "$FEISHU_PY" << 'PATCH_SCRIPT'
import re, sys

feishu_path = sys.argv[1]
marker = "# [FEISHU-TABLE-CARD-PATCH]"

with open(feishu_path, "r", encoding="utf-8") as f:
    src = f.read()

# 1. Insert helper method _build_post_with_md() at class level
# Find the class definition line
class_match = re.search(r'(class FeishuAdapter[^:]*:\s*\n)', src)
if not class_match:
    print("ERROR: Cannot find FeishuAdapter class definition.")
    sys.exit(1)

helper_method = '''
    {marker}
    def _build_post_with_md(self, content: str) -> dict:
        """Build a post+tag:md payload for markdown content containing tables."""
        import json, re
        _TABLE_RE = re.compile(r"^\\|.*\\|\\r?\\n\\|[-|: ]+\\|", re.MULTILINE)
        if not _TABLE_RE.search(content):
            return None
        return {{
            "msg_type": "post",
            "content": {{
                "zh_cn": {{
                    "title": "",
                    "content": [[{{"tag": "md", "text": content}}]],
                }}
            }},
        }}
    {marker}_END
'''.format(marker=marker)

insert_pos = class_match.end()
src = src[:insert_pos] + helper_method + src[insert_pos:]

# 2. Modify _build_outbound_payload to detect tables and use post+tag:md
# Find the _build_outbound_payload method
method_match = re.search(
    r'(def _build_outbound_payload\s*\([^)]*\)\s*[^:]*:\s*\n)',
    src
)
if not method_match:
    print("ERROR: Cannot find _build_outbound_payload method.")
    print("Hermes version may be incompatible. Please patch manually.")
    sys.exit(1)

# Find the first significant code line after the method definition
# We insert our table detection right after the method def line
method_start = method_match.end()

table_detection = '''
        {marker}
        # Detect markdown tables and send as post+tag:md instead of plain text
        post_payload = self._build_post_with_md(content)
        if post_payload:
            return post_payload
        {marker}_SKIP
'''.format(marker=marker)

src = src[:method_start] + table_detection + src[method_start:]

with open(feishu_path, "w", encoding="utf-8") as f:
    f.write(src)

print("Patched FeishuAdapter: added _build_post_with_md() and table detection in _build_outbound_payload")
PATCH_SCRIPT

    # Copy config.json and script to ~/.hermes/skills/productivity/feishu-table-card/scripts/
    SKILLS_DIR="$HOME/.hermes/skills/productivity/feishu-table-card/scripts"
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

    mkdir -p "$SKILLS_DIR"
    cp "$SCRIPT_DIR/scripts/config.json" "$SKILLS_DIR/config.json"
    cp "$SCRIPT_DIR/scripts/feishu_table_card.py" "$SKILLS_DIR/feishu_table_card.py"
    echo "Installed config and script to $SKILLS_DIR"

    echo ""
    echo "Patch applied successfully!"
    echo "Hermes will now send markdown tables as post+tag:md messages."
    echo "Restart Hermes Agent to activate: hermes restart"
}

uninstall_patch() {
    if ! check_patch; then
        echo "Patch not found. Nothing to uninstall."
        return 0
    fi

    # Restore from backup
    if [ -f "${FEISHU_PY}.bak" ]; then
        cp "${FEISHU_PY}.bak" "$FEISHU_PY"
        rm "${FEISHU_PY}.bak"
        echo "Restored feishu.py from backup."
    else
        # Remove patch markers manually
        $PYTHON_CMD - "$FEISHU_PY" << 'UNPATCH_SCRIPT'
import re, sys

feishu_path = sys.argv[1]
marker = "# [FEISHU-TABLE-CARD-PATCH]"
escaped = re.escape(marker)

with open(feishu_path, "r", encoding="utf-8") as f:
    src = f.read()

# Remove everything between MARKER and MARKER_END (inclusive) — helper method
src = re.sub(
    r'\n\s*' + escaped + r'.*?' + escaped + r'_END\n',
    '\n',
    src,
    flags=re.DOTALL,
)

# Remove everything between MARKER and MARKER_SKIP (inclusive) — table detection
src = re.sub(
    r'\n\s*' + escaped + r'.*?' + escaped + r'_SKIP\n',
    '\n',
    src,
    flags=re.DOTALL,
)

with open(feishu_path, "w", encoding="utf-8") as f:
    f.write(src)

print("Removed patch from feishu.py")
UNPATCH_SCRIPT
    fi

    # Remove skill files
    SKILLS_DIR="$HOME/.hermes/skills/productivity/feishu-table-card"
    if [ -d "$SKILLS_DIR" ]; then
        rm -rf "$SKILLS_DIR"
        echo "Removed skill files from $SKILLS_DIR"
    fi

    echo "Patch uninstalled successfully!"
}

case "$action" in
    install)
        install_patch
        ;;
    --uninstall|uninstall)
        uninstall_patch
        ;;
    --check|check)
        if check_patch; then
            echo "Patch is applied."
        else
            echo "Patch is NOT applied."
        fi
        ;;
    *)
        echo "Usage: $0 [install|--uninstall|--check]"
        exit 1
        ;;
esac