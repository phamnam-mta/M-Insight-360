#!/usr/bin/env bash
# SessionStart hook: reminds Claude to check the vendored Superpowers skills
# (.claude/skills/) before responding. Adapted from obra/superpowers'
# hooks/session-start, which normally runs via a plugin's CLAUDE_PLUGIN_ROOT;
# here it reads the skill straight out of this repo instead.
set -euo pipefail

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SKILL_FILE="${PROJECT_ROOT}/.claude/skills/using-superpowers/SKILL.md"

using_superpowers_content=$(cat "$SKILL_FILE" 2>&1 || echo "Error reading using-superpowers skill")

escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

using_superpowers_escaped=$(escape_for_json "$using_superpowers_content")
session_context="<EXTREMELY_IMPORTANT>\nThis repo vendors the Superpowers skills library under .claude/skills/.\n\n**Below is the full content of the 'using-superpowers' skill - your introduction to using skills. For all other skills, use the Skill tool:**\n\n${using_superpowers_escaped}\n</EXTREMELY_IMPORTANT>"

printf '{\n  "hookSpecificOutput": {\n    "hookEventName": "SessionStart",\n    "additionalContext": "%s"\n  }\n}\n' "$session_context"

exit 0
