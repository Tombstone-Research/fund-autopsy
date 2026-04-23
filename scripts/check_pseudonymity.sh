#!/usr/bin/env bash
# Pre-push pseudonymity leak scanner for Fund Autopsy / Tombstone Research.
#
# Scans every file that would be included in a git push against a curated
# list of forbidden identifier patterns. Exits nonzero on any hit so a
# git pre-push hook or CI job can block the push.
#
# Usage:
#   bash scripts/check_pseudonymity.sh
#
# Install as a pre-push hook:
#   ln -sf ../../scripts/check_pseudonymity.sh .git/hooks/pre-push
#   chmod +x .git/hooks/pre-push
#
# Add to CI:
#   - name: Pseudonymity check
#     run: bash scripts/check_pseudonymity.sh
#
# Rationale: the Tombstone pseudonym exists specifically to separate the
# research output from the operator's real-name life. A single leaked
# identifier in a public commit is permanent and defeats the separation.
# This check runs before the push step and fails loudly so the identifier
# can be scrubbed before anything becomes public.

set -u

# Patterns that should never appear in shipped files.
# Case-insensitive grep is applied; patterns are ERE.
FORBIDDEN_PATTERNS=(
  '\bBen\b'
  '\bBenjamin\b'
  'Neubauer'
  'benjaminrneubauer'
  '\bMSPFP\b'
  'financial planning professional'
  'graduate-level financial[- ]planning'
  "master'?s in personal financial planning"
)

# File extensions to scan. Binaries and caches are excluded.
INCLUDE_GLOBS=(
  '*.md'
  '*.py'
  '*.html'
  '*.js'
  '*.css'
  '*.txt'
  '*.yaml'
  '*.yml'
  '*.toml'
  '*.cfg'
  '*.json'
)

# Paths to always exclude even if gitignore doesn't cover them.
# (Defense in depth — the real gate is gitignore.)
EXCLUDE_PATHS=(
  ':(exclude)Intelligence/**'
  ':(exclude).git/**'
  ':(exclude)__pycache__/**'
  ':(exclude)*.pyc'
  ':(exclude).pytest_cache/**'
  ':(exclude).venv/**'
  ':(exclude)venv/**'
  ':(exclude)node_modules/**'
  ':(exclude)tests/fixtures/**'
)

# Move to the repo root regardless of how this script is invoked.
# When run as a pre-push hook, $0 is .git/hooks/pre-push and relative
# path arithmetic sends us into .git/ rather than the working tree.
# git rev-parse --show-toplevel is the canonical answer.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "[pseudonymity] Not inside a git repository; skipping scan." >&2
  exit 2
fi
cd "$REPO_ROOT" || exit 2

# Use git ls-files so we only check files git would actually ship.
# --cached covers tracked files; --others includes untracked but respects
# .gitignore; --exclude-standard filters .gitignore hits.
GIT_FILES=$(git ls-files --cached --others --exclude-standard 2>/dev/null)
if [[ -z "$GIT_FILES" ]]; then
  echo "[pseudonymity] No git-tracked files found; running outside a repo?" >&2
  exit 2
fi

HITS=0
HIT_REPORT=""

while IFS= read -r file; do
  # Skip if not an extension we care about
  case "$file" in
    *.md|*.py|*.html|*.js|*.css|*.txt|*.yaml|*.yml|*.toml|*.cfg|*.json) ;;
    *) continue ;;
  esac

  # Skip excluded paths
  case "$file" in
    Intelligence/*|.git/*|__pycache__/*|*.pyc|.pytest_cache/*|.venv/*|venv/*|node_modules/*|tests/fixtures/*) continue ;;
  esac

  # Skip if file no longer exists (e.g., deleted but still in index)
  [[ -f "$file" ]] || continue

  for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    if grep -i -E -n "$pattern" "$file" >/dev/null 2>&1; then
      HITS=$((HITS + 1))
      match=$(grep -i -E -n "$pattern" "$file" | head -3)
      HIT_REPORT+=$'\n'"  $file  [pattern: $pattern]"$'\n'"$match"$'\n'
    fi
  done
done <<< "$GIT_FILES"

if [[ $HITS -gt 0 ]]; then
  echo "================================================================"
  echo "  PSEUDONYMITY LEAK DETECTED — push blocked"
  echo "================================================================"
  echo "$HIT_REPORT"
  echo
  echo "Scrub the identifiers above or gitignore the files before pushing."
  echo "Run this script again to verify:  bash scripts/check_pseudonymity.sh"
  exit 1
fi

echo "[pseudonymity] Clean. $(echo "$GIT_FILES" | wc -l | tr -d ' ') files scanned across ${#FORBIDDEN_PATTERNS[@]} patterns."
exit 0
