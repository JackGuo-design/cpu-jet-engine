# Contributing

Thanks for looking. This is a small hardware project, so a few conventions keep
it reviewable.

## Before you open a PR

- **Behaviour changes belong in the firmware or the host, not in the docs.** If you
  change a pin, a default duty or a curve, update the matching document in the
  same PR: `docs/en/` and `docs/zh/` are kept in sync.
- **Never change a documented number silently.** Pin numbers, current limits, PWM
  frequency and the fail-safe logic are safety-relevant - explain the change and
  what you measured.
- **Prebuilt firmware must match the source.** If you modify
  `firmware/jetengine_usb/jetengine_usb.ino`, rebuild the merged image, regenerate
  `firmware/prebuilt/SHA256SUMS`, and say in the PR how you verified the flash.

## Style

- Firmware: Arduino/C++, parameters as `static const` at the top of the sketch,
  no magic numbers inline.
- Host tooling: Python 3.10+, standard library plus `pyserial` and `psutil` only.
  No frameworks.
- Documentation: runnable commands in fenced blocks, one idea per section. English
  is the source language; keep the Chinese translation accurate rather than
  literal.

## Regenerating the wiring diagram

```
pip install matplotlib
python tools/make-wiring-diagram.py --lang en
python tools/make-wiring-diagram.py --lang zh   # needs fonts-noto-cjk
```

Commit both PNGs together so the two language versions never drift.

## Reporting a build

Issues are most useful with: board variant (SuperMini clone?), motor model, the
`V` and `?` output, your `engine_config.json`, and whether the fault happens with
`E 1` (switch bypassed) or only with the panel switch in circuit.
