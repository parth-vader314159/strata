#!/usr/bin/env bash
# Build the air-gap bundle. Run ONCE on a CONNECTED machine, then carry
# offline-bundle/ to the isolated host on removable media.
set -euo pipefail
cd "$(dirname "$0")"
OUT=offline-bundle
rm -rf "$OUT"; mkdir -p "$OUT/wheelhouse" "$OUT/images"

echo "==> downloading wheels"
python3 -m pip download -r requirements.txt -d "$OUT/wheelhouse"

echo "==> building and saving the container image"
if command -v docker >/dev/null 2>&1; then
  docker build -t strata/ulpf:2.0.0 .
  docker save strata/ulpf:2.0.0 -o "$OUT/images/strata.tar"
else
  echo "    docker not found — skipping images (a native install still works)"
fi

echo "==> copying source"
for item in strata grammars tests tools docs deck strata.py requirements.txt \
            requirements-dev.txt Dockerfile docker-compose.yml .env.example \
            install-offline.sh pytest.ini Makefile README.md SETUP.md LICENSE; do
  [ -e "$item" ] && cp -r "$item" "$OUT/"
done
chmod +x "$OUT/install-offline.sh"
echo "==> bundle ready: $OUT ($(du -sh "$OUT" | cut -f1))"
