# 1. Circuit design

## 1. System architecture

```
   +--------+  USB-C (5 V + data)  +--------------+   PWM 20 kHz  +---------+  OUT1/2   +--------+
   |   PC   | ------------------> | ESP32-C3     | --1kOhm---->  | DRV8871 | --------> | N30    |
   | Python |                     | SuperMini    |               | H-bridge|           | motor  |
   +--------+                     +------+-------+               +----+----+           +--------+
                                         | GPIO4                      | VM
                                    +----+-----+                +------+------+
                                    |  panel   |                |  12 V PSU   |
                                    |  switch  |                +-------------+
                                    |  -> GND  |
                                    +----------+
                         ESP32 GND / DRV8871 GND / 12 V negative -- common ground
```

**Division of labour**: the ESP32 only does "output PWM on command" plus
watchdog protection. Every speed decision is made on the PC (CPU load mapped to
a duty cycle), so the response curve can be retuned without reflashing the
firmware.

## 2. Bill of materials

| Part | Spec | Qty | Notes |
|---|---|---|---|
| MCU | **ESP32-C3 SuperMini** | 1 | 3.3 V logic, USB-C on board, no extra programmer |
| Motor driver | **DRV8871** module (H-bridge) | 1 | VM 6.5-45 V, 3.6 A peak, has an ILIM pin |
| Motor | **N30** DC motor | 1 | N30 measured in this build; the original design used N20, which had too little torque |
| Power supply | **12 V DC, 1 A** | 1 | Feeds DRV8871 VM only |
| Resistor | 47 kOhm (1/4 W) | 1 | ILIM to GND, sets the current limit |
| Resistor | 1 kOhm (1/4 W) | 1 | In series between GPIO3 and IN1 |
| Switch | latching or momentary, **normally open** | 1 | One side to GPIO4, other side to GND; closed = running allowed |
| Capacitors (recommended) | 100 uF electrolytic + 0.1 uF ceramic | 1 each | Across VM and GND, close to the driver chip |
| Bearings (suggested upgrade) | 6003ZZ x2 + 6204ZZ x2, metal | 4 | Replaces the plastic bearings in kit 006 once a power take-off is fitted - suggested, not required |
| Wire | 0.5 mm^2 or thicker | as needed | Do not use thin wire or breadboard contacts for the motor/12 V loop |

A machine-readable version lives in [`hardware/bom.csv`](../../hardware/bom.csv).

## 3. Design notes

### 3.1 Why IN2 is tied to ground (single direction)

DRV8871 is an H-bridge: the IN1/IN2 combination selects one of four states.

| IN1 | IN2 | Output | Used here |
|---|---|---|---|
| PWM | 0 | Forward, speed controlled | yes - **the combination we use** |
| 0 | PWM | Reverse, speed controlled | no |
| 0 | 0 | **Coast** | yes - the state while stopped |
| 1 | 1 | Brake | no |

With IN2 grounded the model only drives one way. When PWM = 0 both inputs are
low, so the motor coasts instead of braking hard - which sounds much closer to
a real engine spooling down. The model only needs one direction, and this is
the simplest way to get it.

### 3.2 Calculating the current-limit resistor

The DRV8871 current limit is set by the resistor from ILIM to ground:

```
I_limit ~= 64 / R_ILIM(kOhm)   [A]
```

- R = **47 kOhm** -> I_limit ~= **1.36 A**
- For another limit: `R(kOhm) = 64 / I_limit` (e.g. 2 A -> 32 kOhm, 1 A -> 64 kOhm)

**This resistor is not in the motor path** - it only sets an internal comparator
threshold, so 1/4 W is plenty.

An N30 typically draws 0.5-1.5 A. A 1.36 A limit still gives enough inrush to
spin up, while protecting both motor and driver during a stall.

### 3.3 What the 1 kOhm series resistor does

GPIO3 -> 1 kOhm -> IN1. It limits the transient current into IN1 and damps PWM
edge ringing, so the ESP32 pin and the driver input do not fight each other. At
20 kHz it has no effect on the rise time.

### 3.4 Why 20 kHz PWM

- **Above the audible limit (20 kHz)** - you cannot hear the PWM whine.
- Higher frequencies increase DRV8871 switching loss and heating.
- 10-bit resolution (1024 steps) at 20 kHz is easy for the ESP32-C3 LEDC peripheral.

Corresponding firmware constants: `PWM_FREQ = 20000`, `PWM_RES = 10`.

### 3.5 Fail-safe design

The switch logic is **closed to GND = running allowed** (GPIO4 has an internal
pull-up, so a floating pin reads high = OFF):

- switch missing, wire broken, switch failed -> always reads OFF -> motor stays still
- rather than the other way round (must be shorted to stop), where a broken wire
  would mean an out-of-control motor

The firmware adds a second layer: a **2 s watchdog**. After the PC sleeps, shuts
down or the cable is pulled, no command arrives for 2 s and the motor coasts to a
stop. No "walked away, motor still spinning".

### 3.6 Why the supplies are separate

- **ESP32 is powered from USB**: stable voltage, already shares ground with the
  PC, and flashing works.
- **12 V feeds the motor only**: motor start/stop current spikes would brown out
  the MCU if both shared one supply.

They **must share ground** (12 V negative to ESP32 GND), otherwise the PWM signal
has no common reference and the driver sees garbage.

## 4. Electrical quick reference

| Parameter | Value |
|---|---|
| Logic level | 3.3 V (ESP32-C3) |
| PWM frequency / resolution | 20 kHz / 10 bit (1024 steps) |
| Motor supply VM | 12 V (DRV8871 allows 6.5-45 V) |
| Current limit | 1.36 A (R_ILIM = 47 kOhm) |
| Peak capability | DRV8871 rated 3.6 A |
| Idle logic | GPIO4 floating = OFF (no motion) |
| Link-loss protection | 2 s without a command -> coast to stop |
