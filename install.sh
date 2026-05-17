#!/usr/bin/env bash
# install.sh — Patch Hermes Agent to add outgoing:feishu hook point
# Usage: ./install.sh          (install patch)
#        ./install.sh --uninstall  (remove patch)
#        ./install.sh --check      (check if patch is applied)
#
# This script is idempotent and safe: it backs up files before patching,
# and detects existing patches to avoid double-injection.

set -euo pipefail

HERMES_DIR="${HERMES_DIR:-$(pip show hermes-agent 2>/dev/null | grep -oP 'Location: \K.*' | head -1)}"
if [ -z "$HERMES_DIR" ]; then
    # Fallback: try common locations
    for candidate in \
        "$HOME/.local/lib/python3*/site-packages" \
        "/usr/local/lib/python3*/site-packages" \
        "$(python3 -c 'import site; print(site.getsitepackages()[0])' 2>/dev/null)"; do
        if [ -d "$candidate/gateway" ]; then
            HERMES_DIR="$candidate"
            break
        fi
    done
fi

if [ -z "$HERMES_DIR" ]; then
    echo "ERROR: Cannot find Hermes Agent installation directory."
    echo "Set HERMES_DIR environment variable to the site-packages path."
    exit 1
fi

FEISHU_PY="$HERMES_DIR/gateway/platforms/feishu.py"
HOOKS_PY="$HERMES_DIR/gateway/hooks.py"

MARKER="# [FEISHU-TABLE-CARD-HOOK-PATCH]"

action="${1:-install}"

check_patch() {
    if grep -q "$MARKER" "$FEISHU_PY" 2>/dev/null; then
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

    # Patch 1: Insert hook emit + override branch in send() method
    # We insert after "Not connected" check, before format_message()
    python3 << 'PATCH_SCRIPT'
import re, sys

feishu_path = sys.argv[1]
marker = "# [FEISHU-TABLE-CARD-HOOK-PATCH]"

with open(feishu_path, "r", encoding="utf-8") as f:
    src = f.read()

# Find the send() method and insert hook after the "Not connected" early return
# Pattern: after "return SendResult(success=False, error=\"Not connected\")"
# we insert the hook block

hook_block = '''
        {marker}
        hook_results = await self.hooks.emit_collect("outgoing:feishu", {{
            "chat_id": chat_id,
            "content": content,
        }})
        override = None
        for result in hook_results:
            if result and isinstance(result, dict) and "msg_type" in result and "payload" in result:
                override = result
                break
        {marker}_END

        if override:
            response = await self._feishu_send_with_retry(
                chat_id=chat_id,
                msg_type=override["msg_type"],
                payload=override["payload"],
                reply_to=reply_to,
                metadata=metadata,
            )
            return self._finalize_send_result(response, "send failed")
        {marker}_SKIP'''.format(marker=marker)

# Insert after the "Not connected" return in send()
pattern = r'(return SendResult\(success=False, error="Not connected"\)\s*\n)'
match = re.search(pattern, src)
if not match:
    # Try alternate pattern with single quotes
    pattern = r"(return SendResult\(success=False, error='Not connected'\)\s*\n)"
    match = re.search(pattern, src)

if not match:
    print("ERROR: Cannot find 'Not connected' return in send() method.")
    print("Hermes version may be incompatible. Please patch manually.")
    sys.exit(1)

insert_pos = match.end()
src = src[:insert_pos] + hook_block + src[insert_pos:]

with open(feishu_path, "w", encoding="utf-8") as f:
    f.write(src)

print("Patched send() method in feishu.py")
PATCH_SCRIPT
    "$FEISHU_PY"

    # Copy hook files to ~/.hermes/hooks/
    HOOKS_DIR="$HOME/.hermes/hooks/feishu-table-card-hook"
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    SKILL_HOOKS_DIR="$SCRIPT_DIR/hooks/feishu-table-card-hook"

    mkdir -p "$HOOKS_DIR"
    cp "$SKILL_HOOKS_DIR/HOOK.yaml" "$HOOKS_DIR/HOOK.yaml"
    cp "$SKILL_HOOKS_DIR/handler.py" "$HOOKS_DIR/handler.py"
    echo "Installed hook files to $HOOKS_DIR"

    echo ""
    echo "Patch applied successfully!"
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
        python3 << 'UNPATCH_SCRIPT'
import re, sys

feishu_path = sys.argv[1]
marker = "# [FEISHU-TABLE-CARD-HOOK-PATCH]"

with open(feishu_path, "r", encoding="utf-8") as f:
    src = f.read()

# Remove everything between MARKER and MARKER_SKIP (inclusive)
src = re.sub(
    r'\n\s*' + marker + r'.*?' + marker + r'_SKIP\n',
    '\n',
    src,
    flags=re.DOTALL,
)

with open(feishu_path, "w", encoding="utf-8") as f:
    f.write(src)

print("Removed patch from feishu.py")
UNPATCH_SCRIPT
        "$FEISHU_PY"
    fi

    # Remove hook files
    HOOKS_DIR="$HOME/.hermes/hooks/feishu-table-card-hook"
    if [ -d "$HOOKS_DIR" ]; then
        rm -rf "$HOOKS_DIR"
        echo "Removed hook files from $HOOKS_DIR"
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