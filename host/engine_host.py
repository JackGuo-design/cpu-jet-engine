#!/usr/bin/env python3
"""
engine_host.py —— 在 USB 所连的那台电脑上运行，测本机 CPU 占用率，
通过 USB 串口把目标占空比发给 ESP32-C3（喷气发动机模型驱动板）。

为什么必须在电脑侧测：ESP32 是被 USB 主机枚举的从设备，它没有任何办法
读到主机的 CPU 占用率。所以"测 CPU"这件事只能由电脑上的这个小程序做。

用法：
    python engine_host.py                 # 正常跟随 CPU
    python engine_host.py --manual 55     # 手动固定 duty（台架测试）
    python engine_host.py --dry-run       # 不接串口，只打印将要发送的 duty
    python engine_host.py --port COM7     # 指定串口（默认按 VID 303A:1001 自动找）

依赖：psutil、pyserial。  退出时发 "S" 让模型滑行停转；
即使本程序被强杀，固件 2 秒收不到心跳也会自己停。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    sys.exit("缺少 psutil：pip install psutil")

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

ESP_VID = 0x303A          # Espressif
ESP_PID_NATIVE = 0x1001   # C3/S3 原生 USB-JTAG/CDC

HERE = Path(__file__).resolve().parent
CFG_PATH = HERE / "engine_config.json"


# ---------------------------------------------------------------- 配置
DEFAULT_CFG = {
    "port": None,                 # None = 自动扫描
    "baud": 115200,
    "device_vid": ESP_VID,
    "device_pid": ESP_PID_NATIVE,
    # 每档：[CPU 上限(不含), duty%]；最后一档上限写 100
    "bands": [
        {"cpu": 8,   "duty": 30},
        {"cpu": 25,  "duty": 42},
        {"cpu": 50,  "duty": 55},
        {"cpu": 75,  "duty": 70},
        {"cpu": 100, "duty": 88},
    ],
    "hysteresis": 4,              # 迟滞 ±4 个百分点
    "upshift_samples": 2,         # 升档需连续 N 次（约 N 秒）
    "downshift_samples": 4,       # 降档需连续 N 次（慢回落 = 惯性感）
    "sample_interval": 1.0,       # 采样周期 s
    "idle_duty": 30,              # 开机/无负载时怠速
    "log_file": "engine_host.log",
    "log_status_every_s": 10,
}


def load_cfg() -> dict:
    cfg = dict(DEFAULT_CFG)
    if CFG_PATH.exists():
        try:
            cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[cfg] {CFG_PATH} 读不了，用默认值：{e}")
    return cfg


# ---------------------------------------------------------------- 串口
def find_port(port: str | None, vid: int, pid: int) -> str | None:
    if port:
        return port
    if list_ports is None:
        return None
    cands = list(list_ports.comports())
    # 1) 先按 VID/PID 精确匹配
    for p in cands:
        if p.vid == vid and (pid == 0 or p.pid == pid):
            return p.device
    # 2) 再按描述兜底
    for p in cands:
        d = f"{p.description} {p.hwid}".lower()
        if "espressif" in d or "usb jtag" in d:
            return p.device
    return None


def open_port(cfg: dict) -> "serial.Serial | None":
    if serial is None:
        return None
    dev = find_port(cfg["port"], cfg["device_vid"], cfg["device_pid"])
    if not dev:
        return None
    try:
        sp = serial.Serial(dev, cfg["baud"], timeout=0.05, write_timeout=0.5)
        time.sleep(0.3)
        sp.reset_input_buffer()
        return sp
    except Exception as e:
        print(f"[serial] 打不开 {dev}: {e}")
        return None


def send(sp, line: str) -> bool:
    try:
        sp.write((line + "\n").encode())
        sp.flush()
        return True
    except Exception:
        return False


def drain_reports(sp, sink: dict) -> None:
    """非阻塞读 MCU 回报，缓存最后一行。"""
    try:
        while sp.in_waiting:
            raw = sp.readline()
            if not raw:
                break
            txt = raw.decode(errors="replace").strip()
            if txt:
                sink["last"] = txt
                if txt.startswith("#"):
                    sink["note"] = txt
                elif txt.startswith("R"):
                    p = txt.split()
                    if len(p) >= 6:
                        sink["mcu_duty"] = p[1]
                        sink["sw"] = p[5]
    except Exception:
        pass


# ---------------------------------------------------------------- 映射
class BandMapper:
    def __init__(self, cfg: dict):
        self.bands = cfg["bands"]
        self.h = int(cfg["hysteresis"])
        self.up_n = max(1, int(cfg["upshift_samples"]))
        self.down_n = max(1, int(cfg["downshift_samples"]))
        self.band = 0
        self.up = 0
        self.down = 0

    def duty_for(self, cpu: float) -> int:
        b = self.band
        hi = self.bands[b]["cpu"]                 # 本档上限（不含）
        lo = self.bands[b - 1]["cpu"] if b > 0 else 0.0
        self.up = self.up + 1 if (b < len(self.bands) - 1 and cpu > hi + self.h) else 0
        self.down = self.down + 1 if (b > 0 and cpu < lo - self.h) else 0
        if self.up >= self.up_n:
            self.band += 1
            self.up = 0
            self.down = 0
        elif self.down >= self.down_n:
            self.band -= 1
            self.up = 0
            self.down = 0
        return int(self.bands[self.band]["duty"])


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", type=float, help="固定 duty（0-90），不做 CPU 跟随")
    ap.add_argument("--dry-run", action="store_true", help="不打开串口，仅打印")
    ap.add_argument("--port", help="串口设备，如 /dev/ttyACM0 或 COM7")
    ap.add_argument("--seconds", type=float, default=0, help="跑多少秒后退出（0=一直跑）")
    args = ap.parse_args()

    cfg = load_cfg()
    if args.port:
        cfg["port"] = args.port
    interval = float(cfg["sample_interval"])

    logpath = HERE / cfg.get("log_file", "engine_host.log")

    def log(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line)
        try:
            with open(logpath, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    log(f"=== engine_host start (manual={args.manual} dry={args.dry_run}) ===")

    sp = None if args.dry_run else open_port(cfg)
    if not args.dry_run and sp is None:
        log("[serial] 没找到 ESP32（VID 303A:1001），先跑着，插上后自动连")
    elif sp is not None:
        log(f"[serial] opened {sp.port} @{cfg['baud']}")
        send(sp, "V")
        time.sleep(0.2)

    mapper = None if args.manual is not None else BandMapper(cfg)
    psutil.cpu_percent(interval=None)          # 第一次调用只是初始化
    sink: dict = {}
    last_duty = None
    t0 = time.time()
    next_status = t0 + float(cfg.get("log_status_every_s", 10))

    try:
        while True:
            if args.seconds and time.time() - t0 >= args.seconds:
                break
            time.sleep(interval)

            if args.manual is not None:
                duty = int(max(0, min(90, args.manual)))
                cpu = None
            else:
                cpu = psutil.cpu_percent(interval=None)
                duty = mapper.duty_for(cpu)

            if sp is None and not args.dry_run:
                sp = open_port(cfg)
                if sp is not None:
                    log(f"[serial] opened {sp.port} @{cfg['baud']}")

            if sp is not None and not args.dry_run:
                # 每秒都发 = 心跳（固件 2 s 超时）
                if not send(sp, f"T {duty}"):
                    log("[serial] 写失败，准备重连")
                    try:
                        sp.close()
                    except Exception:
                        pass
                    sp = None
                else:
                    drain_reports(sp, sink)
            if args.dry_run:
                pass

            now = time.time()
            if now >= next_status:
                next_status = now + float(cfg.get("log_status_every_s", 10))
                cpu_s = f"{cpu:5.1f}%" if cpu is not None else "  n/a"
                band_s = mapper.band if mapper else "-"
                sw = sink.get("sw")
                sw_s = "on" if sw == "1" else ("off" if sw == "0" else "?")
                log(f"cpu={cpu_s} band={band_s} duty={duty} sw={sw_s} "
                    f"mcu={sink.get('last', '-')}")
                if sw == "0":
                    log("[switch] 面板开关处于关闭状态(GPIO4 未接地)：电机被硬件禁止，"
                        "打开开关后立刻按当前档位起转")
            elif duty != last_duty:
                log(f"cpu={cpu:5.1f}% band={mapper.band} duty={duty} -> dev" if cpu is not None
                    else f"duty={duty} -> dev")
            last_duty = duty
    except KeyboardInterrupt:
        log("Ctrl+C 退出")
    finally:
        if sp is not None:
            send(sp, "S")
            time.sleep(0.1)
            try:
                sp.close()
            except Exception:
                pass
        log("=== engine_host stop, 已发 S ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
