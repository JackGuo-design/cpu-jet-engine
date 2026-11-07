# 3. Firmware

## 0. Read this first

This firmware is the **USB-CDC serial** variant: the ESP32-C3 USB connector is
both the flashing port and the command port. No USB-TTL adapter needed.

- **Prebuilt image**: `firmware/prebuilt/jetengine_full.bin` (4 MB, bootloader +
  partition table + application merged, flash it at address `0x0`)
- **Firmware version**: `jetengine-usb 1.1`
- **Target chip**: ESP32-C3, 4 MB flash
- **Checksums**: see the end of this document

---

## Option A: flash the prebuilt image (recommended, one command)

### A1. Install esptool

```bash
pip install esptool
```

### A2. Find the serial port

| OS | Device name |
|---|---|
| Windows | `COM3`, `COM7`, ... (Device Manager -> Ports (COM & LPT)) |
| Linux | `/dev/ttyACM0` (or `/dev/ttyUSB0`) |
| macOS | `/dev/cu.usbmodem*` |

### A3. Flash

```bash
# Windows
esptool.py --chip esp32c3 --port COM7 --baud 921600 write_flash 0x0 jetengine_full.bin

# Linux / macOS
esptool.py --chip esp32c3 --port /dev/ttyACM0 --baud 921600 write_flash 0x0 jetengine_full.bin
```

**If you get "Failed to connect"**: put the board into download mode - hold
`BOOT`, tap `RST` (or unplug/replug USB), release `BOOT`, then rerun the command.

### A4. Verify

Unplug and replug USB, then open the port with any serial tool (**115200 8N1**).
You should immediately see:

```
# jetengine-usb 1.0  ESP32-C3 SuperMini + DRV8871
# pwm=GPIO3 20kHz  min=15%  max=100%  idle=80%  kick=+10%  wd=2000ms  ramp=75%/s
# switch(GPIO4) = OFF   (E 1 = bypass switch)
```

> The `1.0` on the first line is a stale string left in the source; it does not
> affect behaviour, and the `V` command returns the accurate `1.1`.
> No output at all -> in nine cases out of ten the image was built without
> `CDCOnBoot=cdc` (relevant when you compile with option B).

---

## Option B: build from source (when you need to change parameters)

### B1. Install arduino-cli + the ESP32 core

```bash
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32          # 3.3.11 is what this project was verified with
```

### B2. Compile (copy the FQBN exactly)

```bash
cd firmware/jetengine_usb
arduino-cli compile \
  --fqbn "esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M,PartitionScheme=default" \
  --build-path build .
```

All three options are required:

| Option | Consequence if omitted |
|---|---|
| `CDCOnBoot=cdc` | **the USB serial port never appears**, the PC cannot see the board |
| `FlashSize=4M` | partition table generated for the wrong capacity, may not boot |
| `PartitionScheme=default` | different partition layout, merged-image addresses no longer line up |

### B3. Upload

```bash
arduino-cli upload \
  --fqbn "esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M,PartitionScheme=default" \
  --port /dev/ttyACM0 --input-dir build .
```

### B4. Build the merged single-file image (for distribution)

```bash
cd build
esptool.py --chip esp32c3 merge_bin -o jetengine_full.bin \
  --flash_mode dio --flash_freq 80m --flash_size 4MB \
  0x0 jetengine_usb.ino.bootloader.bin \
  0x8000 jetengine_usb.ino.partitions.bin \
  0xe000 boot_app0.bin \
  0x10000 jetengine_usb.ino.bin
```

---

## 2. Firmware parameters (values in this build)

Change these at the top of the `.ino` file, then rebuild and reflash with option B.

| Constant | Value | Meaning |
|---|---|---|
| `PIN_PWM` | **3** | PWM output (to 1 kOhm -> IN1) |
| `PIN_SW` | **4** | enable switch input (internal pull-up, GND = allowed) |
| `PIN_LED` | **8** | on-board LED (active low) |
| `PWM_FREQ` | **20000** | 20 kHz, above the audible band |
| `PWM_RES` | **10 bit** | 1024 steps |
| `DUTY_MAX` | **100 %** | upper limit |
| `DUTY_MIN_RUN` | **15 %** | **running floor (low-speed dead zone)** - any non-zero target below it is lifted to it |
| `DUTY_IDLE` | **80 %** | idle value used by the `I` command (a normal `T` is unaffected) |
| `RAMP_PER_SEC` | **75 %/s** | slew rate, 0 -> 90% in about 1.2 s |
| `KICK_ABS` | **45 %** | minimum absolute value of the start-up kick |
| `KICK_BOOST` | **+10 %** | kick = max(target + 10, 45) |
| `KICK_MS` | **250 ms** | how long the kick lasts before falling back to the target |
| `WD_MS` | **2000 ms** | watchdog: 2 s without any command -> coast to stop |
| `REPORT_MS` | **200 ms** | status report rate, 5 Hz (`R` lines) |

### `DUTY_MIN_RUN` is the parameter you must retune per motor

It used to be **80**, because the N20 motor could not overcome static friction
below 75% and stopped after a few seconds. The N30 has enough torque, so it came
down to **15**.

**If you use a different motor**, run the calibration procedure at the end of
docs/en/04-host-software.md and set your own value. Do not copy 15 blindly.

---

## 3. Command set (typed into the serial terminal, terminated with `\n`)

| Command | Effect |
|---|---|
| `T <0-100>` | set the target duty. **Also the heartbeat** - 2 s without one and the motor stops |
| `I` | idle (equivalent to `T DUTY_IDLE`, 80% here) |
| `S` | stop (target to zero, coasts down along the ramp) |
| `K` | clear fault |
| `?` | report status immediately |
| `V` | version and parameters |
| `P` | pin self test: prints the raw level of nine candidate GPIOs at once |
| `E <0\|1>` | `E 1` = bypass the panel switch and force "running allowed" (debug only, resets to 0 on power cycle) |

### Status report format (5 Hz)

```
R <duty> <target> <state> <ms since last command> <sw>
R 30.0 30.0 RUN 951 1
```

| Field | Meaning |
|---|---|
| `duty` | actual duty now (the value during a ramp) |
| `target` | target duty (note: low values are lifted to `DUTY_MIN_RUN`) |
| `state` | `IDLE` / `RUN` / `COAST` |
| `ms since last command` | milliseconds since the last command; above 2000 triggers the coast |
| `sw` | 1 = running allowed, 0 = blocked by the switch |

**Debugging rule of thumb**: `target` differs from what you sent -> dead-zone
lift; `sw=0` -> check the switch wiring; `ms` keeps climbing -> the host is not
sending heartbeats.

---

## 4. Image checksums

```
file:            jetengine_full.bin
size:            4194304 bytes (4.0 MB)
MD5:             84b0c6ec5366f372e2a34747fba70b68
SHA-256:         2c0a539a4ee603bf30aa8bb2f73d94f1d5d4f6018610f0d9bc9492a57c00c569
application MD5: 0a24143235ade111d5cb4f65dbda97c0
```

Check it before flashing (Windows: `certutil -hashfile jetengine_full.bin SHA256`;
Linux/macOS: `shasum -a 256`). The same hashes are in
`firmware/prebuilt/SHA256SUMS`.
