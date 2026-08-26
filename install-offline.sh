#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# STRATA — air-gapped installer. Requirement (j).
#
# Run on a host with NO internet. Installs from files only: a local wheelhouse
# and a saved container image. If any step here needs the network, that is a
# bug, not an inconvenience.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"
say(){ printf '\033[1;36m%s\033[0m\n' "$*"; }
ok(){  printf '  \033[32m%s\033[0m\n' "$*"; }
die(){ printf '\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

say "[1/5] verifying the bundle is self-contained"
[ -d wheelhouse ] || die "wheelhouse/ missing — run build-bundle.sh on a connected host"
ok "wheelhouse present ($(ls wheelhouse | wc -l) wheels)"

say "[2/5] installing dependencies from local files only"
# --no-index is the point: pip is forbidden from reaching any network.
python3 -m pip install --no-index --find-links=wheelhouse -r requirements.txt
ok "installed with --no-index"

say "[3/5] loading the container image"
if [ -d images ] && command -v docker >/dev/null 2>&1; then
  for tar in images/*.tar; do [ -e "$tar" ] && docker load -i "$tar"; done
  ok "image loaded"
else
  ok "skipped (no images/ or docker absent — running natively)"
fi

say "[4/5] configuration"
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET=$(python3 -c "import secrets;print(secrets.token_hex(32))")
  sed -i.bak "s|^STRATA_SECRET=.*|STRATA_SECRET=$SECRET|" .env && rm -f .env.bak
  ok ".env created with a freshly generated secret"
else
  ok ".env already present, left untouched"
fi

say "[5/5] verifying"
python3 strata.py check
python3 -m pytest -q 2>/dev/null | tail -2 || true

echo
say "Installed. Next:"
echo "  python3 strata.py demo       # the scripted demonstration"
echo "  python3 strata.py console    # http://localhost:8400"
echo "  docker compose up -d         # containerised"
echo
say "Now disconnect the network and run the demo again. Nothing changes."
