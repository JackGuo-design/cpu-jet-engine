# 四、固件烧录说明

> 中文原版。英文版见 [`docs/en/03-firmware.md`](../en/03-firmware.md)。本文档采用 CC BY-SA 4.0 授权，见 [`LICENSE-docs`](../../LICENSE-docs)。

## 0. 先看这里

本固件是 **USB-CDC 串口版**：ESP32-C3 的 USB 口既是烧录口也是通信口，插上就能烧，不需要 USB-TTL 模块。

- **烧录镜像**：`firmware/jetengine_full.bin`（4 MB，已合并 bootloader + 分区表 + 应用，从地址 `0x0` 烧）
- **固件版本**：`jetengine-usb 1.1`
- **目标芯片**：ESP32-C3（4 MB Flash）
- **校验值**：见本文件末

---

## 方式 A：直接烧现成镜像（推荐，一个命令）

### A1. 装 esptool

```bash
pip install esptool
```

### A2. 找到串口

| 系统 | 设备名 |
|---|---|
| Windows | `COM3` / `COM7` …（设备管理器 → 端口(COM 和 LPT)） |
| Linux | `/dev/ttyACM0`（或 `/dev/ttyUSB0`） |
| macOS | `/dev/cu.usbmodem*` |

### A3. 烧录

```bash
# Windows
esptool.py --chip esp32c3 --port COM7 --baud 921600 write_flash 0x0 jetengine_full.bin

# Linux / macOS
esptool.py --chip esp32c3 --port /dev/ttyACM0 --baud 921600 write_flash 0x0 jetengine_full.bin
```

**如果报 "Failed to connect"**：让板子进下载模式 —— 按住 `BOOT` 键不放，点一下 `RST`（或拔插一次 USB），再松开 BOOT，然后重跑上面的命令。

### A4. 烧完直接验证

拔插一次 USB，用任意串口工具打开（**115200，8N1**），你应该马上看到：

```
# jetengine-usb 1.0  ESP32-C3 SuperMini + DRV8871
# pwm=GPIO3 20kHz  min=15%  max=100%  idle=80%  kick=+10%  wd=2000ms  ramp=75%/s
# switch(GPIO4) = OFF   (E 1 = bypass switch)
```

> 第一行的 `1.0` 是源码里遗留的旧字符串（不影响功能），`V` 命令返回的才是准确的 `1.1`。
> 看不到输出 → 九成是烧的时候没带 `CDCOnBoot=cdc`（用方式 B 编译时一定要注意）。

---

## 方式 B：从源码编译（要改参数时用）

### B1. 装 arduino-cli + ESP32 核心

```bash
# 安装 arduino-cli（各平台见 https://arduino.github.io/arduino-cli/）
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32          # 本项目用 3.3.11 验证通过
```

### B2. 编译（FQBN 必须完全照抄）

```bash
cd firmware
arduino-cli compile \
  --fqbn "esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M,PartitionScheme=default" \
  --build-path build .
```

三个参数缺一不可：

| 参数 | 不写的后果 |
|---|---|
| `CDCOnBoot=cdc` | **USB 串口根本不出现**，电脑认不到板子 |
| `FlashSize=4M` | 分区表按错误容量生成，可能起不来 |
| `PartitionScheme=default` | 分区布局变化，合并镜像地址对不上 |

### B3. 上传

```bash
arduino-cli upload \
  --fqbn "esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M,PartitionScheme=default" \
  --port /dev/ttyACM0 --input-dir build .
```

### B4. 生成合并镜像（要做成单文件分发时）

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

## 2. 固件参数表（本版实际值）

改这些值在 `.ino` 文件顶部，改完按方式 B 重新编译烧录。

| 常量 | 值 | 含义 |
|---|---|---|
| `PIN_PWM` | **3** | PWM 输出脚（接 1kΩ → IN1） |
| `PIN_SW` | **4** | 使能开关输入（内部上拉，接 GND = 允许转） |
| `PIN_LED` | **8** | 板载 LED（低电平点亮） |
| `PWM_FREQ` | **20000** | 20 kHz，避开人耳听觉 |
| `PWM_RES` | **10 bit** | 1024 级分辨率 |
| `DUTY_MAX` | **100 %** | 上限 |
| `DUTY_MIN_RUN` | **15 %** | **运行下限（低速死区）** ——任何非零目标低于此值会被抬上来 |
| `DUTY_IDLE` | **80 %** | `I` 命令用的怠速值（正常 T 命令不受影响） |
| `RAMP_PER_SEC` | **75 %/s** | 斜坡速率，0→90% 约 1.2 秒 |
| `KICK_ABS` | **45 %** | 起转冲量的最小绝对值 |
| `KICK_BOOST` | **+10 %** | 起转在目标上再加 10%　→ 实际冲量 = max(目标+10, 45) |
| `KICK_MS` | **250 ms** | 冲量维持时间，之后回落到目标值 |
| `WD_MS` | **2000 ms** | 看门狗：2 秒无任何命令 → 滑行停转 |
| `REPORT_MS` | **200 ms** | 状态回报频率 5 Hz（`R` 行） |

### ⚠️ `DUTY_MIN_RUN` 是最需要按电机调整的参数

它原本是 **80**，因为 N20 电机在 75% 以下撑不住静摩擦、转几秒就停。换成 N30 之后扭矩足够，才降到 **15**。

**如果你用别的电机**，照 [04-host-software.md](04-host-software.md) 末节的标定流程重新确定这个值，不要直接照搬 15。

---

## 3. 命令集（串口里直接敲，`\n` 结尾）

| 命令 | 作用 |
|---|---|
| `T <0-100>` | 设目标占空比。**同时是心跳**，2 秒不发就自动停 |
| `I` | 怠速（等于 `T DUTY_IDLE`，本版 80%） |
| `S` | 停机（目标归零，按斜坡滑行） |
| `K` | 清故障 |
| `?` | 立即回报一次状态 |
| `V` | 版本与参数 |
| `P` | 引脚自检：一次打印 9 个候选 GPIO 的原始电平 |
| `E <0\|1>` | `E 1` = 绕过面板开关强制允许转（调试用，断电复位为 0） |

### 状态回报格式（5 Hz）

```
R <duty> <target> <state> <ms自上次命令> <sw>
R 30.0 30.0 RUN 951 1
```

| 字段 | 含义 |
|---|---|
| `duty` | 当前实际占空比（斜坡中的值） |
| `target` | 目标占空比（注意：低速值会被抬到 `DUTY_MIN_RUN`） |
| `state` | `IDLE` / `RUN` / `COAST` |
| `ms自上次命令` | 距上次收到命令的毫秒数，超过 2000 会触发滑行 |
| `sw` | 1 = 允许转，0 = 被开关禁止 |

**排查口诀**：`target` 和你发的值不一样 → 死区抬升；`sw=0` → 查开关接线；`ms` 一直涨 → 主机没在发心跳。

---

## 4. 镜像校验

```
文件名: jetengine_full.bin
大小:   4194304 字节 (4.0 MB)
MD5:    84b0c6ec5366f372e2a34747fba70b68
应用段 MD5: 0a24143235ade111d5cb4f65dbda97c0
```

烧录前建议核对一下 MD5（Windows: `certutil -hashfile jetengine_full.bin MD5`；Linux: `md5sum`）。
