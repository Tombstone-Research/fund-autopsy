"""Centralized identity and configuration.

All public-facing identity strings live here. When bootstrapping under a
pseudonym, update this single file — every module, header, and template
reads from these values.
"""

# ── Public Identity ──────────────────────────────────────────────────────────
# Change these when setting up the fresh pseudonym / GitHub / email.
# Everything else in the codebase references these values.

ORG_NAME = "Tombstone Research"
ORG_TAGLINE = "Leave no stone unturned."
PROJECT_NAME = "Fund Autopsy"

# EDGAR requires a real contact email in the User-Agent header.
# SEC policy: https://www.sec.gov/os/accessing-edgar-data
# Use the pseudonym email once it's created.
CONTACT_EMAIL = "fundautopsy@tombstoneresearch.com"

# GitHub
GITHUB_ORG = "tombstoneresearch"
GITHUB_REPO = "fund-autopsy"
GITHUB_URL = f"https://github.com/{GITHUB_ORG}/{GITHUB_REPO}"

# ── EDGAR Access ─────────────────────────────────────────────────────────────
# SEC rate limit: 10 requests/second. We stay slightly under.
EDGAR_USER_AGENT = (
    f"{PROJECT_NAME}/0.1.0 ({CONTACT_EMAIL}; open-source fund cost analyzer)"
)
EDGAR_RATE_LIMIT_DELAY = 0.12  # seconds between requests

# ── Application ──────────────────────────────────────────────────────────────
APP_VERSION = "0.1.0"
