# Credits and third-party licences

This repository contains **only** the electronics and software work: the ESP32-C3
firmware, the PC-side host program, the wiring design and the documents that
describe them. The printed airframe and the mechanical power take-off are
**other people's designs** and are **not** redistributed here.

Read this before you fork, repackage or publish anything based on this repo.

## 1. Printed model (airframe) - NOT included

| | |
|---|---|
| Title | **3D Printable Low Bypass Turbofan** (build instructions Rev A) |
| Designer | **CATIAV5FTW** |
| Where to get it | MakerWorld global: <https://makerworld.com/en/models/744985> |
| | MakerWorld China: <https://makerworld.com.cn/zh/models/599135> |
| Licence | **MakerWorld Exclusive License** |

The licence terms, as published on the model page (2026-11):

> This user content is protected by the MakerWorld Exclusive License. You may
> create derivative works based on this object, but all such derivative works
> must be published **only on the MakerWorld platform**, and must credit the
> original creator.

What that means in practice:

- **No STL/3MF/STEP files, no assembly PDF, no remixes belong in this
  repository.** Download the model from MakerWorld yourself, under that licence.
- If you remix the airframe (a different motor mount, a modified casing, a
  stand), publish the remix **on MakerWorld only**, with credit to CATIAV5FTW.
- The official build instructions (Rev A PDF, 25 pages) are part of that model's
  download and are not reproduced or linked as a file here.

## 2. Mechanical power take-off - NOT included

| | |
|---|---|
| Title | **低旁通涡扇发动机动力组件** (low-bypass turbofan power components) |
| Designer | **炒面大师 / @sinnercool** |
| Where to get it | <https://makerworld.com.cn/models/1455937> |
| Licence | **CC BY-NC 4.0** (Attribution-NonCommercial) |

This is the printed motor mount / drive hardware that turns the fan inside the
model. Its licence requires attribution and forbids commercial use.

- Attribution must be kept if you redistribute anything derived from it.
- Because of the **NC** term, a build that includes this part is **not licensed
  for commercial use**, whatever the electronics licences in this repo say.
- Its files are not included here either.

## 3. Hardware kit

The airframe is designed around **Bambu Lab "Jet Engine Model Components Kit
006"** (sold as MH006), which supplies the bearings, screws, nuts and washers.
That is a commercial product and is not covered by any licence in this repo.

## 4. This project's own work

| Material | Author | Licence |
|---|---|---|
| Firmware, host program, tooling (`firmware/`, `host/`, `tools/`) | BH8UMP | MIT ([LICENSE](LICENSE)) |
| Wiring design, BOM, figures (`hardware/`, `docs/assets/`) | BH8UMP | CERN-OHL-S-2.0 ([LICENSE-hardware](LICENSE-hardware)) |
| Documentation (`docs/`, README, this file, CHANGELOG) | BH8UMP | CC BY-SA 4.0 ([LICENSE-docs](LICENSE-docs)) |

The printed **control box** (`hardware/control-box-v2.3mf`) is also original to
this project and is published under CERN-OHL-S-2.0 like the rest of the hardware
design.

The original contribution is the **drive system**: USB-serial control link, 20 kHz
PWM with ramping and start-up kick, the fail-safe switch/watchdog design, the
CPU-load mapping and calibration workflow. It replaces the knob-type speed
controller that the mechanical power components assume.

Commodity parts used here (ESP32-C3 SuperMini, DRV8871 module, N30 DC motor) are
off-the-shelf components; no attribution is required, and their own datasheets
and terms apply.

## 5. If you publish a fork

1. Keep this file, and keep the three-way licence split intact.
2. Do not add model files, remixes or the official PDFs to your fork.
3. Do not describe the result as commercially usable while it includes the
   CC BY-NC power components.
4. Credit CATIAV5FTW for the airframe and 炒面大师 / @sinnercool for the power
   components wherever you show the assembled model - those are the parts people
   will actually see.
