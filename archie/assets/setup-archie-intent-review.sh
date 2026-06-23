#!/usr/bin/env bash
# setup-archie-intent-review.sh
#
# Idempotent setup for the Archie Intent Review GitHub Action.
# Prereq checks, secure secret setup, workflow install (copies the canonical
# YAML — no embedded duplicate), Actions probe, fork-PR caveat.
#
# Usage: bash setup-archie-intent-review.sh
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-.}"
WORKFLOW_FILE="${REPO_ROOT}/.github/workflows/archie-intent-review.yml"

log_info()    { echo -e "${BLUE}i ${NC}$*"; }
log_success() { echo -e "${GREEN}OK ${NC}$*"; }
log_warn()    { echo -e "${YELLOW}! ${NC}$*"; }
log_error()   { echo -e "${RED}x ${NC}$*"; }
die() { log_error "$1"; exit 1; }

# Resolve the canonical workflow YAML (single source of truth). Priority:
#  1. .archie/workflows/  (if the npx bundle ever places it there)
#  2. <script dir>/workflows/  (running from a checked-out asset bundle)
resolve_workflow_src() {
    local candidates=(
        "${REPO_ROOT}/.archie/workflows/archie-intent-review.yml"
        "${SCRIPT_DIR}/workflows/archie-intent-review.yml"
    )
    for c in "${candidates[@]}"; do
        if [ -f "$c" ]; then printf '%s\n' "$c"; return 0; fi
    done
    return 1
}

# ===== SECTION 1: PREREQUISITES =====
log_info "Checking prerequisites..."

git rev-parse --git-dir >/dev/null 2>&1 || die "Not inside a git repository. Run from the repo root."
log_success "Inside a git repository"

git config --get remote.origin.url >/dev/null 2>&1 || die "No 'origin' remote found."
log_success "Git remote 'origin' found"

command -v gh >/dev/null 2>&1 || die "gh CLI not found. Install from https://github.com/cli/cli or 'brew install gh'."
log_success "gh CLI is installed ($(gh --version | head -1))"

gh auth status >/dev/null 2>&1 || die "gh CLI not authenticated. Run 'gh auth login' first."
GITHUB_ACCOUNT="$(gh api user --jq .login)"
log_success "gh authenticated as ${GITHUB_ACCOUNT}"

[ -f "${REPO_ROOT}/.archie/blueprint.json" ] || die ".archie/blueprint.json not found. Run '/archie-deep-scan' first to establish the baseline."
log_success ".archie/blueprint.json baseline exists"

WORKFLOW_SRC="$(resolve_workflow_src)" || die "Canonical workflow YAML not found (looked in .archie/workflows/ and ${SCRIPT_DIR}/workflows/). Reinstall archie assets."
log_success "Canonical workflow YAML resolved: ${WORKFLOW_SRC}"

# ===== SECTION 2: SECRET SETUP =====
log_info "Setting up ANTHROPIC_API_KEY secret (available to GitHub Actions on this repo)..."
printf 'Enter your ANTHROPIC_API_KEY (will not be displayed): '
read -rs ANTHROPIC_API_KEY
echo ""
[ -n "$ANTHROPIC_API_KEY" ] || die "ANTHROPIC_API_KEY cannot be empty."

printf '%s' "$ANTHROPIC_API_KEY" | gh secret set ANTHROPIC_API_KEY
unset ANTHROPIC_API_KEY
log_success "ANTHROPIC_API_KEY secret set (stored encrypted on GitHub)"

# ===== SECTION 3: WORKFLOW INSTALL (copy canonical, no heredoc) =====
log_info "Installing workflow file..."
mkdir -p "$(dirname "$WORKFLOW_FILE")"
cp "$WORKFLOW_SRC" "$WORKFLOW_FILE"
log_success "Workflow installed at ${WORKFLOW_FILE} (byte-identical to canonical)"

# ===== SECTION 4: ACTIONS ENABLEMENT PROBE (advisory) =====
log_info "Probing GitHub Actions (advisory only)..."
REPO_SLUG="$(git config --get remote.origin.url | sed 's|.*github.com[:/]||; s|\.git$||')"
if gh workflow list -R "$REPO_SLUG" >/dev/null 2>&1; then
    log_success "Actions appear enabled (probe is advisory; verify in repo settings if unsure)"
else
    log_warn "Could not verify Actions status — you may need to enable Actions on GitHub"
fi

# ===== SECTION 5: SUMMARY & CAVEATS =====
log_success "Setup complete."
echo ""
echo "Next steps:"
echo "  1. Commit .github/workflows/archie-intent-review.yml"
echo "  2. Push and open a PR"
echo "  3. The Action posts an FYI comment on the PR"
echo ""
echo -e "${YELLOW}Fork PR limitation:${NC}"
echo "  - Uses the 'pull_request' event (non-blocking FYI)."
echo "  - Fork PRs cannot access repo secrets; the Action skips silently on them."
echo "  - To cover fork PRs, 'pull_request_target' is a security tradeoff (out of scope)."
echo ""
log_info "To rotate the key later: gh secret set ANTHROPIC_API_KEY"
log_info "Design doc: docs/archie-intent-review-design.md"
