# 五、主机程序（电脑端）

> 中文原版。英文版见 [`docs/en/04-host-software.md`](../en/04-host-software.md)。本文档采用 CC BY-SA 4.0 授权，见 [`LICENSE-docs`](../../LICENSE-docs)。

电脑端负责"测 CPU 占用 → 换算成目标转速 → 持续发命令当心跳"。曲线逻辑全在这里，调参不用重烧固件。

## 1. 安装依赖

```bash
pip install pyserial psutil
```

| 库 | 用途 |
|---|---|
| `pyserial` | 打开串口、发命令 |
| `psutil` | 读取 CPU 占用率 |

## 2. 运行

```bash
# 自动找 ESP32（按 VID:PID = 303A:1001）
python engine_host.py

# 指定串口
python engine_host.py --port /dev/ttyACM0      # Linux
python engine_host.py --port COM7              # Windows

# 固定占空比（不跟 CPU，纯手动测电机）
python engine_host.py --manual 40

# 只看不连（dry-run，验证曲线逻辑）
python engine_host.py --dry-run

# 跑 60 秒后自动退出
python engine_host.py --seconds 60
```

**Ctrl+C 退出时会发 `S` 让电机滑行停转**，不会卡在转的状态。

## 3. 配置文件 `engine_config.json`

```json
{
  "port": null,              // null = 自动找；或写死 "/dev/ttyACM0" / "COM7"
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

  "hysteresis": 4,           // 换档迟滞：跨过档位界限 4% 才算数
  "upshift_samples": 2,      // 升档需连续 2 次采样命中
  "downshift_samples": 4,    // 降档需连续 4 次采样（更慢，避免抖动）
  "sample_interval": 1.0,    // 采样周期（秒）——同时是发送心跳的周期
  "idle_duty": 30,           // 启动/怠速占空比
  "log_file": "engine_host.log",
  "log_status_every_s": 10   // 日志里每隔多久打印一次状态
}
```

### 本机已标定好的曲线（N30 电机）

| CPU 区间 | duty |
|---|---|
| < 8% | **30%**（启动/怠速，实测可稳定运行） |
| 8 ~ 25% | 45% |
| 25 ~ 50% | 60% |
| 50 ~ 75% | 80% |
| ≥ 75% | 100% |

相邻档跨度 15~20 个百分点，转速变化是连续的，不会"窜一下"。

### 调曲线的两个原则

1. **最低档必须 ≥ 你电机的 `DUTY_MIN_RUN`**（本版固件 15%）。设得更低也会被固件抬上来，白改。
2. **相邻档差距不要超过 25 个百分点**，否则 CPU 一波动就有明显的转速突变。

## 4. ⭐ 换电机后必须做的标定

`DUTY_MIN_RUN` 是"这台电机能持续转起来的最低占空比"。不同电机差别极大：

- N20（原设计）：需要 80% 才撑得住静摩擦，75% 转几秒就停
- N30（本项目）：15% 就够了，30% 能稳定运行

### 标定流程

**第 1 步：扫档**

```bash
# 每档 12 秒，自动绕过面板开关
python sweep_duty.py /dev/ttyACM0 15,20,25,30,40,50 12
```

盯住电机，记下**每一档能不能持续转满 12 秒**（不是"能不能动一下"）。

**第 2 步：确定下限**

取"能持续转"的最小档位，再往下减 3~5% 作为安全余量：

| 扫档结果 | 建议 DUTY_MIN_RUN |
|---|---|
| 25% 起能稳转 | 20 |
| 30% 起能稳转 | 25 |
| 40% 起能稳转 | 35 |

**第 3 步：写进固件并重烧**

改 `.ino` 里的 `DUTY_MIN_RUN`，按 [03-firmware.md](03-firmware.md) 的方式 B 重新编译烧录。

**第 4 步：把主机曲线的最低档也调成同值以上**

改 `engine_config.json` 的 `idle_duty` 和 `bands[0].duty`。

> 为什么两个地方都要改：固件的 `DUTY_MIN_RUN` 是**硬保护**（防止低速堵转发热），主机曲线的 `idle_duty` 是**实际想跑的值**。两者要匹配，否则你会看到发 20 但实际跑 25 的现象。

## 5. 日志

运行时会写 `engine_host.log`，每 10 秒一行，格式：

```
2026-11-05 21:06:13 cpu=  2.0% band=0 duty=30 sw=on mcu=R 30.0 30.0 RUN 951 1
```

| 字段 | 含义 |
|---|---|
| `cpu=` | 当前 CPU 占用 |
| `band=` | 落在第几档（0~4） |
| `duty=` | 发给固件的目标值 |
| `sw=` | 面板开关状态 |
| `mcu=` | 固件回报的原始 `R` 行 |

**排查时看 `mcu=` 后面那两个数**：`R 30.0 30.0` 表示固件实际执行 30、目标也是 30。如果第二个数和你发的 `duty` 不一致，就是被 `DUTY_MIN_RUN` 抬升了。

## 6. 常见问题

| 现象 | 原因 |
|---|---|
| `找不到设备` | 固件没带 `CDCOnBoot=cdc`；或 VID/PID 不匹配（改 `device_vid/pid`） |
| 电机转 2 秒就停，日志里 `ms` 一直涨 | 主程序没跑或卡住，心跳断了（看门狗保护） |
| CPU 占用很高但电机不加速 | `sample_interval` 太长，采样点落在低负载瞬间；改为 0.5 |
| 转速频繁忽高忽低 | 把 `hysteresis` 加到 6~8，或把 `upshift_samples` 加到 3 |
| 关掉程序电机还在转 | 正常，会滑行 1~2 秒停下；若不停说明看门狗没生效，检查固件版本 |
