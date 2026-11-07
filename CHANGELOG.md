# Changelog

All notable changes to this project. Version numbers track the firmware, since
that is what people flash.

## [1.1.0] - 2026-11-06

First public release.

- Firmware `jetengine-usb 1.1`: USB-CDC command link, 20 kHz PWM, duty ramp,
  start-up kick, panel-switch fail-safe, 2 s command watchdog.
- N30 motor support: `DUTY_MIN_RUN` lowered from 80% (N20) to 15%.
- Host program: CPU-load band mapping with hysteresis, heartbeat, manual mode,
  dry-run mode, status logging.
- `sweep_duty.py` for calibrating `DUTY_MIN_RUN` on a new motor.
- Prebuilt merged flash image for ESP32-C3 (4 MB) with published hashes.
- Documentation in English and Chinese, wiring diagram in both languages.
- Build photos of the finished model in `docs/assets/`, and the printed control
  box design (`hardware/control-box-v2.3mf`) under CERN-OHL-S-2.0.
- BOM revised after the build: 12 V 1 A supply, metal bearings (6003ZZ x2 +
  6204ZZ x2) listed as a suggested upgrade over the plastic kit bearings.
- Licensing: MIT (code), CERN-OHL-S-2.0 (hardware), CC BY-SA 4.0 (docs).
- `CREDITS.md`: attribution and licence terms for the third-party 3D designs this
  project drives (CATIAV5FTW airframe - MakerWorld Exclusive; 炒面大师 power
  components - CC BY-NC 4.0; Bambu Lab kit 006). No third-party model files are
  redistributed.

### Known issues

- Boot banner still prints `jetengine-usb 1.0` (stale string in the source; the
  `V` command reports 1.1 correctly).
- No audio output - the project drives the motor only.

## Earlier iterations (pre-release)

- WiFi HTTP variant: the ESP32 served a small web endpoint and the host POSTed a
  duty value. Replaced by USB serial - one cable for both flashing and control,
  no credentials to manage.
- N20 motor variant: could not overcome static friction below 75% duty; replaced
  with the N30.
