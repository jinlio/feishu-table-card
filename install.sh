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

HERMES_DIR="${HERMES_DIR:-$($PYTHON_CMD -c "
import importlib.util, os
spec = importlib.util.find_spec('gateway')
if spec and spec.origin:
    base = spec.origin.rsplit('/',1)[0]
    feishu_path = os.path.join(base, 'gateway', 'platforms', 'feishu.py')
    if os.path.isfile(feishu_path):
        print(base)
" 2>/dev/null || true)}"

if [ -z "$HERMES_DIR" ]; then
    HERMES_DIR="$($PYTHON_CMD -c "
import site, glob, os
for sp in site.getsitepackages() + [site.getusersitepackages()]:
    feishu_path = os.path.join(sp, 'gateway', 'platforms', 'feishu.py')
    if os.path.isfile(feishu_path):
        print(sp)
        break
else:
    for pattern in [os.path.expanduser('~/.virtualenvs/*/lib/python3*/site-packages'),
                    '/opt/venvs/*/lib/python3*/site-packages',
                    '/usr/lib/python3/dist-packages',
                    '/usr/local/lib/python3*/dist-packages',
                    '/usr/lib64/python3*/site-packages']:
        for d in glob.glob(pattern):
            feishu_path = os.path.join(d, 'gateway', 'platforms', 'feishu.py')
            if os.path.isfile(feishu_path):
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
class_match = re.search(r'(class FeishuAdapter\s*\([^)]*\)\s*:\s*\n)', src)
if not class_match:
    print("ERROR: Cannot find FeishuAdapter class definition.")
    sys.exit(1)

# Detect indentation style from existing methods in the class
indent_match = re.search(r'\n(\s+)def \w+', src[class_match.end():])
indent_str = indent_match.group(1) if indent_match else "    "

helper_method = '''
{indent_str}{marker}
{indent_str}def _build_post_with_md(self, content: str) -> dict:
{indent_str}    """Build a post+tag:md payload for markdown content containing tables."""
{indent_str}    import json, re
{indent_str}    def _has_markdown_table(text):
{indent_str}        lines = text.split("\\n")
{indent_str}        i = 0
{indent_str}        while i < len(lines):
{indent_str}            stripped = lines[i].strip()
{indent_str}            if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 2:
{indent_str}                if i + 1 < len(lines):
{indent_str}                    sep = lines[i + 1].strip()
{indent_str}                    if sep.startswith("|") and sep.endswith("|"):
{indent_str}                        cells = sep.strip("|").split("|")
{indent_str}                        if all(re.match(r"^\\s*[-:]+\\s*$", c) for c in cells):
{indent_str}                            return True
{indent_str}            i += 1
{indent_str}        return False
{indent_str}    if not _has_markdown_table(content):
{indent_str}        return None
{indent_str}    return {{
{indent_str}        "zh_cn": {{
{indent_str}            "title": "",
{indent_str}            "content": [[{{"tag": "md", "text": content}}]],
{indent_str}        }}
{indent_str}    }}
{indent_str}{marker}_END
'''.format(marker=marker, indent_str=indent_str)

insert_pos = class_match.end()
src = src[:insert_pos] + helper_method + src[insert_pos:]

# 2. Modify _build_outbound_payload to detect tables and use post+tag:md
# Find the _build_outbound_payload method and extract the content parameter name
method_match = re.search(
    r'def _build_outbound_payload\s*\([^)]*\)\s*[^:]*:\s*\n',
    src
)
if not method_match:
    print("ERROR: Cannot find _build_outbound_payload method.")
    print("Hermes version may be incompatible. Please patch manually.")
    sys.exit(1)

# Verify this is the exact method (not a variant like _build_outbound_payload_async)
method_name = re.search(r'def (\w+)', src[method_match.start():method_match.end()])
if method_name and method_name.group(1) != "_build_outbound_payload":
    print("ERROR: Found method variant '" + method_name.group(1) + "' instead of '_build_outbound_payload'.")
    print("Hermes version may be incompatible. Please patch manually.")
    sys.exit(1)

# Extract the parameter that holds the message content
# Look for common parameter names: content, text, message, body, msg, outbound_text
method_sig = src[method_match.start():method_match.end()]
params_match = re.search(r'\(([^)]*)\)', method_sig)
param_names = []
if params_match:
    param_names = re.findall(r'(\w+)\s*:', params_match.group(1))
    if not param_names:
        param_names = re.findall(r'(\w+)[,\)]', params_match.group(1))

content_var = None
for candidate in ['content', 'text', 'message', 'body', 'msg', 'outbound_text']:
    if candidate in param_names:
        content_var = candidate
        break

if not content_var:
    # Fallback: use the last positional parameter (excluding self)
    non_self = [p for p in param_names if p != 'self']
    if non_self:
        content_var = non_self[-1]
    else:
        print("ERROR: Cannot determine content parameter name in _build_outbound_payload.")
        print("Method signature: " + method_sig.strip())
        sys.exit(1)

method_start = method_match.end()

table_detection = '''
        {marker}
        # Detect markdown tables and send as post+tag:md instead of plain text
        post_payload = self._build_post_with_md({content_var})
        if post_payload:
            return "post", json.dumps(post_payload, ensure_ascii=False)
        {marker}_SKIP
'''.format(marker=marker, content_var=content_var)

src = src[:method_start] + table_detection + src[method_start:]

with open(feishu_path, "w", encoding="utf-8") as f:
    f.write(src)

print("Patched FeishuAdapter: added _build_post_with_md() and table detection in _build_outbound_payload")
PATCH_SCRIPT

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

# Remove helper method: exact marker line -> exact marker_END line
helper_start = src.find(marker + '\n')
while helper_start != -1:
    helper_end = src.find(marker + '_END\n', helper_start)
    if helper_end == -1:
        break
    end_pos = helper_end + len(marker) + len('_END\n')
    src = src[:helper_start] + src[end_pos:]
    helper_start = src.find(marker + '\n')

# Remove table detection: exact marker line -> exact marker_SKIP line
detect_start = src.find(marker + '\n')
while detect_start != -1:
    detect_end = src.find(marker + '_SKIP\n', detect_start)
    if detect_end == -1:
        break
    end_pos = detect_end + len(marker) + len('_SKIP\n')
    src = src[:detect_start] + src[end_pos:]
    detect_start = src.find(marker + '\n')

with open(feishu_path, "w", encoding="utf-8") as f:
    f.write(src)

print("Removed patch from feishu.py")
UNPATCH_SCRIPT
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