# 4. Host software (PC side)

The PC is responsible for "measure CPU load -> map it to a target speed -> keep
sending commands as a heartbeat". All curve logic lives here, so retuning needs no
reflash.

## 1. Install dependencies

```bash
pip install -r host/requirements.txt     # pyserial, psutil
```

| Library | Purpose |
|---|---|
| `pyserial` | open the serial port, send commands |
| `psutil` | read the CPU utilisation |

## 2. Run

```bash
# auto-detect the ESP32 (by VID:PID = 303A:1001)
python host/engine_host.py

# explicit port
python host/engine_host.py --port /dev/ttyACM0      # Linux
python host/engine_host.py --port COM7              # Windows

# fixed duty, no CPU tracking (bench testing)
python host/engine_host.py --manual 40

# print only, no serial port (verify the curve logic)
python host/engine_host.py --dry-run

# run for 60 s then exit
python host/engine_host.py --seconds 60
```

**On Ctrl+C the host sends `S`**, so the motor coasts down instead of being left
spinning.

## 3. Configuration file `host/engine_config.json`

```json
{
  "port": null,              // null = auto-detect; or "/dev/ttyACM0" / "COM7"
  "baud": 115200,
  "device_vid": 12346,       // 0x303A = Espressif
  "device_pid": 4097,        // 0x1001 = ESP32-C3 USB-CDC

  "bands": [
    {"cpu": 8,   "duty": 30},
    {"cpu": 25,  "duty": 45},
    {"cpu": 50,  "duty": 60},
    {"cpu": 75,  "duty": 80},
    {"cpu": 100, "duty": 100}
  ],

  "hysteresis": 4,           // band-change hysteresis: 4% past a boundary before it counts
  "upshift_samples": 2,      // consecutive hits needed to shift up
  "downshift_samples": 4,    // consecutive hits needed to shift down (slower, avoids flutter)
  "sample_interval": 1.0,    // sampling period in seconds - also the heartbeat period
  "idle_duty": 30,           // start-up / idle duty
  "log_file": "engine_host.log",
  "log_status_every_s": 10   // how often a status line is written to the log
}
```

Note: JSON does not support comments - the annotations above are for reading
only. Use the committed file as-is.

### The curve calibrated in this build (N30 motor)

| CPU range | duty |
|---|---|
| < 8% | **30%** (start-up / idle, verified stable) |
| 8 - 25% | 45% |
| 25 - 50% | 60% |
| 50 - 75% | 80% |
| >= 75% | 100% |

Adjacent bands are 15-20 percentage points apart, so speed changes feel
continuous rather than snapping.

### Two rules when editing the curve

1. **The lowest band must be >= your motor's `DUTY_MIN_RUN`** (15% in this
   firmware). Anything lower is lifted by the firmware anyway.
2. **Keep adjacent bands within 25 percentage points**, otherwise any CPU
   fluctuation produces an obvious jump in speed.

## 4. Calibration after changing the motor (mandatory)

`DUTY_MIN_RUN` is "the lowest duty at which this motor keeps turning". It varies
enormously between motors:

- N20 (original design): needed 80% to overcome static friction; at 75% it ran a
  few seconds and stopped
- N30 (this build): 15% is enough, and 30% runs stably

### Procedure

**Step 1: sweep the bands**

```bash
# 12 s per step, panel switch bypassed automatically
python host/sweep_duty.py /dev/ttyACM0 15,20,25,30,40,50 12
```

Watch the motor and record **whether each step keeps turning for the full 12 s**
(not "whether it twitched").

**Step 2: pick the floor**

Take the lowest step that keeps running, then subtract 3-5% as margin:

| Sweep result | Suggested `DUTY_MIN_RUN` |
|---|---|
| stable from 25% | 20 |
| stable from 30% | 25 |
| stable from 40% | 35 |

**Step 3: write it into the firmware and reflash**

Edit `DUTY_MIN_RUN` in the `.ino` and rebuild/flash with option B in
docs/en/03-firmware.md.

**Step 4: raise the host curve's lowest band to match**

Edit `idle_duty` and `bands[0].duty` in `host/engine_config.json`.

> Both places matter: the firmware's `DUTY_MIN_RUN` is a **hard protection** (it
> prevents a stalled low-speed motor from overheating), while the host's
> `idle_duty` is **the speed you actually want**. If they disagree you will send
> 20 and observe 25.

## 5. Logging

A run writes `engine_host.log`, one line every 10 s:

```
2026-11-05 21:06:13 cpu=  2.0% band=0 duty=30 sw=on mcu=R 30.0 30.0 RUN 951 1
```

| Field | Meaning |
|---|---|
| `cpu=` | current CPU utilisation |
| `band=` | which band matched (0-4) |
| `duty=` | target value sent to the firmware |
| `sw=` | panel switch state |
| `mcu=` | the raw `R` line reported by the firmware |

**When debugging, look at the two numbers after `mcu=`**: `R 30.0 30.0` means the
firmware is running 30 with a target of 30. If the second number differs from the
`duty` you sent, `DUTY_MIN_RUN` lifted it.

## 6. FAQ

| Symptom | Cause |
|---|---|
| `device not found` | firmware built without `CDCOnBoot=cdc`; or VID/PID mismatch (edit `device_vid`/`device_pid`) |
| Motor stops after 2 s, `ms` in the log keeps climbing | the host is not running or is stuck, heartbeat lost (watchdog protection) |
| High CPU load but the motor does not speed up | `sample_interval` too long, samples land in low-load gaps; set it to 0.5 |
| Speed flaps up and down | raise `hysteresis` to 6-8, or `upshift_samples` to 3 |
| Motor keeps running after the app exits | expected - it coasts for 1-2 s. If it never stops, the watchdog is not working; check the firmware version |
