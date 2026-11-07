# Hardware

The build is a module-level wiring project: an ESP32-C3 SuperMini board, a
DRV8871 driver module and an N30 motor on a 12 V supply. There is no custom PCB
and no CAD source - the authoritative "design" is the pinout and the wiring
diagram.

- [`bom.csv`](bom.csv) - bill of materials, machine readable
- [`control-box-v2.3mf`](control-box-v2.3mf) - printed enclosure for the
  electronics: toggle switch at the front; DC jack, motor leads and USB at the
  rear. Original design, published under CERN-OHL-S-2.0.
- [`../docs/assets/wiring-diagram.png`](../docs/assets/wiring-diagram.png) - wiring overview
- [`../docs/en/01-circuit-design.md`](../docs/en/01-circuit-design.md) - why each
  component value is what it is
- [`../docs/en/02-assembly.md`](../docs/en/02-assembly.md) - pinout tables and the
  assembly order

Key values:

| Item | Value | Why |
|---|---|---|
| PWM frequency | 20 kHz | above the audible band |
| Current limit | 1.36 A | 47 kOhm from ILIM to GND: `I = 64 / R(kOhm)` |
| Series resistor | 1 kOhm | GPIO3 -> IN1, damps the PWM edge |
| Motor supply | 12 V | DRV8871 VM range is 6.5-45 V; ESP32 stays on USB power |
| Switch logic | closed to GND = run | internal pull-up, so a broken wire means "stop" |

If you fit a different motor, re-derive the current limit from its rated current
and recalibrate `DUTY_MIN_RUN` as described in `../docs/en/04-host-software.md`.
