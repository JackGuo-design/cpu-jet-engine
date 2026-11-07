# 2. Wiring and assembly

**Prerequisites**: the printed airframe (CATIAV5FTW, MakerWorld 744985) and the
printed power components (炒面大师, MakerWorld CN 1455937), assembled following
their own instructions. Attribution and licence terms: [CREDITS.md](../../CREDITS.md).
This document covers the electronics only.

Read this together with the wiring overview
([`docs/assets/wiring-diagram.png`](../assets/wiring-diagram.png)).
**Order matters: signals first, then ground, then 12 V and the motor last.**

## 1. Pinout

### ESP32-C3 SuperMini side

| Silkscreen | Connect to | Notes |
|---|---|---|
| `GPIO3` (some boards print `3`) | -> 1 kOhm -> DRV8871 `IN1` | 20 kHz PWM output |
| `GPIO4` (prints `4`) | -> one side of the switch | internal pull-up; the other side goes to GND |
| `GND` | -> common ground | must be tied to the 12 V negative |
| `5V` / `VBUS` | not connected | the board is powered over USB-C |
| `GPIO8` | not connected | on-board LED, driven by the firmware (active low) |

> Warning: SuperMini silkscreens differ between vendors. **Confirm the pin with a
> multimeter or with the firmware's `P` command before soldering** (`P` prints the
> live level of nine candidate GPIOs).

### DRV8871 module side

| Module pin | Connect to | Notes |
|---|---|---|
| `VM` | 12 V positive | motor supply, **never connect it to the ESP32** |
| `GND` | common ground | same node as ESP32 GND and 12 V negative |
| `IN1` | <- 1 kOhm <- GPIO3 | PWM input |
| `IN2` | GND | fixed low = single direction |
| `ILIM` | 47 kOhm -> GND | sets the 1.36 A limit |
| `OUT1` | one motor terminal | swap with OUT2 if the direction is wrong |
| `OUT2` | the other motor terminal | |

> Some DRV8871 modules already have the ILIM resistor fitted (30k/47k are common).
> **If the module has one, do not add another** - read the value printed on it first.

## 2. Wiring steps (in order)

**Step 1: signal wires (power off)**

1. GPIO3 -> 1 kOhm -> DRV8871 `IN1`
2. GPIO4 -> one side of the switch
3. DRV8871 `IN2` -> common ground
4. DRV8871 `ILIM` -> 47 kOhm -> common ground (skip if the module has one)

**Step 2: ground wires (critical - do not skip)**

5. ESP32 `GND` -> common ground
6. DRV8871 `GND` -> common ground
7. other side of the switch -> common ground

> Use a terminal block, or twist and solder the three ground wires together.
> **Do not pass more than 1 A through breadboard spring contacts.**

**Step 3: decoupling capacitors**

8. 100 uF electrolytic (mind the polarity: positive to VM) + 0.1 uF ceramic,
   in parallel between DRV8871 `VM` and `GND`, as close to the chip as possible

**Step 4: motor**

9. Motor leads to `OUT1` / `OUT2` (still no 12 V at this point)

**Step 5: power**

10. 12 V positive -> DRV8871 `VM`
11. 12 V negative -> common ground

## 3. Power-up self test (follow this - do not just plug the motor in)

| Step | Action | Expected result |
|---|---|---|
| 1 | USB only, **no 12 V, no motor** | a serial port appears (Windows: Device Manager -> Ports; Linux: `/dev/ttyACM0`) |
| 2 | open the port at 115200 | boot banner: `# jetengine-usb ... ESP32-C3 SuperMini + DRV8871` |
| 3 | send `V` | one line with version and parameters: `# jetengine-usb 1.1 pwm=GPIO3 20kHz idle=80% kick=45% max=100% wd=2000ms` |
| 4 | send `P` | nine GPIO levels, to find which pin the switch is really on |
| 5 | flip the switch, send `P` or `?` | the pin wired to GND toggles between 0 and 1 |
| 6 | connect 12 V (still no motor), measure `OUT1`-`OUT2` with a meter | after `T 50` you should read about 12 V x 50% = 6 V DC |
| 7 | power off, connect the motor, power up again | close the switch -> motor spins; open it -> coasts to a stop |

> Step 6 is what separates "does the driver have output" from "can this motor
> spin". If there is no voltage there, the fault is in the driver or the wiring,
> not the motor.

## 4. Bench commands (type them into the serial terminal, terminated with `\n`)

| Command | Effect |
|---|---|
| `T 30` | target 30% speed (also the heartbeat - 2 s without one and the motor stops) |
| `T 0` or `S` | stop (coast) |
| `T 100` | full speed |
| `?` | report status once, immediately |
| `V` | version and parameters |
| `P` | pin self test |
| `E 1` | **bypass the panel switch** and force "running allowed" (for debugging the motor path; resets to 0 on power cycle) |
| `K` | clear fault |

> Handy when troubleshooting: `E 1` + `T 50` removes the switch from the equation
> and tests the motor path directly.

## 5. Troubleshooting

| Symptom | Most likely cause |
|---|---|
| No serial port at all | firmware flashed without `CDCOnBoot=cdc`; or a charge-only USB cable |
| Port exists but commands do nothing | wrong baud rate (115200); or the terminal sends `\r\n` (normally fine) |
| `P` shows GPIO4 stuck at 0 | switch wired normally-closed, or the wire touches GND (firmware then thinks the switch is closed = always allowed) |
| `R` reports a higher target than you sent | you sent a low value and the firmware lifted it to `DUTY_MIN_RUN` (15% in this build, so normally not an issue) |
| Motor just twitches | duty below the static-friction threshold of this motor -> raise the target, or recalibrate `DUTY_MIN_RUN` per docs/en/04 |
| Spins then stops | the host stopped sending commands (heartbeat lost) -> is `engine_host.py` still running? |
| Motor runs, then stops itself after 2 s | same: watchdog timeout. Keep the host `sample_interval` <= 1.0 s |
| Driver hot, motor weak | current limit set too low (ILIM resistor too large); or the supply sags under load (the 1 A adapter is fine in normal running, but a stalled motor drags it down) |
| Motor hums but does not turn, and the 12 V rail sags | normal. The DRV8871 limit is 1.36 A while the reference adapter supplies 1 A, so a stalled motor pulls the rail down - the adapter's own limit protects it, nothing burns, but a sagging rail makes voltage measurements look wrong. Clear the jam, or raise the supply if you need to stall-test |
| ESP32 reboots repeatedly | 12 V noise reaching the 5 V rail, or missing common ground; check the decoupling caps and wiring |
