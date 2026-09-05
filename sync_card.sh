#!/bin/bash
# Copy card/ onto the projector's SD card.
#
# Uses `cat` rather than `cp` on purpose: macOS writes an AppleDouble "._name"
# sidecar next to any file carrying extended attributes, and the projector may
# choke enumerating those -- they are not ILDA files. `cat` moves bytes only.
set -euo pipefail
CARD="${1:-/Volumes/NO NAME}/picture"

[ -d "$(dirname "$CARD")" ] || { echo "card not mounted at $(dirname "$CARD")"; exit 1; }
mkdir -p "$CARD"

echo "clearing old contents..."
rm -f "$CARD"/*.ild "$CARD"/*.ILD "$CARD"/Picture.prg "$CARD"/._* 2>/dev/null || true

echo "copying..."
for f in card/*; do
  cat "$f" > "$CARD/$(basename "$f")"
done

xattr -c "$CARD"/* 2>/dev/null || true
dot_clean -m "$(dirname "$CARD")" 2>/dev/null || true
rm -f "$CARD"/._* 2>/dev/null || true

echo
echo "on card:"
ls -la "$CARD" | grep -v '^total'
echo
if find "$CARD" -name '._*' | grep -q .; then
  echo "WARNING: macOS metadata files still present"; exit 1
fi
echo "playlist entries resolve:"
tr -d '\r' < "$CARD/Picture.prg" | while IFS=, read -r f a b; do
  [ -z "$f" ] && continue
  [ -f "$CARD/$f" ] && echo "  OK      $f" || { echo "  MISSING $f"; exit 1; }
done
echo
echo "done - eject with: diskutil eject '$(dirname "$CARD")'"
