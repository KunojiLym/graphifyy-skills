# shellcheck shell=bash
# Ad-hoc-safe resolver (paste into agent shells or: eval "$(sed -n '/^resolve_graphifyy_skills_root/,/^}/p' lib/resolve_skills_root.sh)")
resolve_graphifyy_skills_root() {
  local cwd="${1:-$(pwd)}"
  local home="${2:-$HOME}"
  local hint="${GRAPHIFYY_SKILL_DIR:-}"
  local candidate roots

  if [[ -n "$hint" && -f "$hint/ipynb_split.py" && -f "$(dirname "$hint")/databricks-graphify/lvdash_split.py" ]]; then
    printf '%s\n' "$(cd "$(dirname "$hint")" && pwd)"
    return 0
  fi
  if [[ -n "$hint" && -f "$hint/lvdash_split.py" && -f "$(dirname "$hint")/ipynb-graphify/ipynb_split.py" ]]; then
    printf '%s\n' "$(cd "$(dirname "$hint")" && pwd)"
    return 0
  fi
  if [[ -n "${BASH_SOURCE[1]:-}" ]]; then
    local src_dir
    src_dir="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
    if [[ -f "$src_dir/ipynb_split.py" ]]; then
      printf '%s\n' "$(cd "$(dirname "$src_dir")" && pwd)"
      return 0
    fi
    if [[ -f "$src_dir/lvdash_split.py" ]]; then
      printf '%s\n' "$(cd "$(dirname "$src_dir")" && pwd)"
      return 0
    fi
  fi

  if [[ -n "${GRAPHIFYY_SKILLS_ROOT:-}" ]]; then
    roots="$GRAPHIFYY_SKILLS_ROOT"
  else
    roots="$cwd $cwd/.claude/skills/graphifyy-skills $home/.claude/skills/graphifyy-skills $cwd/.cursor/skills/graphifyy-skills"
  fi

  for candidate in $roots; do
    if [[ -f "$candidate/ipynb-graphify/ipynb_split.py" && -f "$candidate/databricks-graphify/lvdash_split.py" ]]; then
      printf '%s\n' "$(cd "$candidate" && pwd)"
      return 0
    fi
  done

  echo "error: graphifyy-skills not found (tried project-local .claude/skills, global ~/.claude/skills, .cursor/skills). Set GRAPHIFYY_SKILLS_ROOT." >&2
  return 1
}
