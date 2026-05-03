#!/usr/bin/env bash
# Build the React portal and write assets to printechs_support/public/portal/
#
# Usage (from the printechs_support app directory):
#   ./scripts/build-portal.sh
#
# For a separate portal origin (Option C), set the bench URL before building:
#   VITE_FRAPPE_SITE_URL=https://your-erpnext-host.example.com ./scripts/build-portal.sh
#
# Then on the bench (same machine or CI):
#   bench migrate
#   bench --site <site> clear-cache
#   bench restart
#
# Add allow_cors for your portal origin to site_config.json or common_site_config.json
# (see portal/frappe-site-config.cors.example.json). Static files are under:
#   apps/printechs_support/printechs_support/public/portal/

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/portal"

if [[ -z "${VITE_FRAPPE_SITE_URL:-}" ]]; then
	echo "Note: VITE_FRAPPE_SITE_URL is unset. Building for same-origin (embedded portal on the bench host)."
	echo "      For Option C, run: VITE_FRAPPE_SITE_URL=https://your-bench-url ./scripts/build-portal.sh"
	echo ""
fi

if [[ -f package-lock.json ]]; then
	npm ci
else
	npm install
fi

npm run build

echo ""
echo "Portal assets written to: $ROOT/printechs_support/public/portal/"
echo "Next: bench migrate && bench clear-cache && bench restart"
echo "      Merge allow_cors for your portal URL (see portal/frappe-site-config.cors.example.json)."
echo "      Deploy static files if the portal is hosted outside the bench (nginx, CDN, etc.)."
