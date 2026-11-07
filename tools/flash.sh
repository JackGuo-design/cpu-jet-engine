#!/usr/bin/env bash
# Flash the prebuilt CPU Jet Engine image to an ESP32-C3.
#
#   ./tools/flash.sh                 # auto-detect the port
#   ./tools/flash.sh /dev/ttyACM0    # explicit port
#
# Verifies the published SHA-256 before writing. Requires esptool on PATH
# (pip install esptool).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMG="$REPO/firmware/prebuilt/jetengine_full.bin"
SUMS="$REPO/firmware/prebuilt/SHA256SUMS"

[ -f "$IMG" ] || { echo "missing image: $IMG" >&2; exit 1; }
command -v esptool.py >/dev/null 2>&1 || {
  echo "esptool.py not found - pip install esptool" >&2; exit 1; }

# --- checksum ---------------------------------------------------------------
want="$(awk '$2 == "jetengine_full.bin" {print $1}' "$SUMS")"
if command -v sha256sum >/dev/null 2>&1; then
  got="$(sha256sum "$IMG" | awk '{print $1}')"
else
  got="$(shasum -a 256 "$IMG" | awk '{print $1}')"
fi
if [ "$want" != "$got" ]; then
  echo "checksum mismatch: expected $want, got $got" >&2
  exit 1
fi
echo "image OK ($got)"

# --- port -------------------------------------------------------------------
PORT="${1:-}"
if [ -z "$PORT" ]; then
  PORT="$(ls /dev/ttyACM* /dev/cu.usbmodem* 2>/dev/null | head -n1 || true)"
  [ -n "$PORT" ] || { echo "no serial port found - pass one explicitly" >&2; exit 1; }
  echo "auto-detected port: $PORT"
fi

echo "flashing $IMG -> $PORT"
esptool.py --chip esp32c3 --port "$PORT" --baud 921600 \
  write_flash 0x0 "$IMG"

echo
echo "done. open $PORT at 115200 and press the RST button if nothing appears."
