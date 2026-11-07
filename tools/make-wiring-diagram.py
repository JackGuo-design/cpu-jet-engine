#!/usr/bin/env python3
"""Generate the wiring overview figure for the CPU Jet Engine project.

Usage:
    python tools/make-wiring-diagram.py --lang en   # -> docs/assets/wiring-diagram.png
    python tools/make-wiring-diagram.py --lang zh   # -> docs/assets/wiring-diagram.zh-CN.png

Requires matplotlib. For --lang zh a CJK font must be installed
(Noto Sans CJK SC is picked up automatically when present).

The figure is a system-level wiring overview, not a schematic. Pin numbers and
component values match docs/en/01-circuit-design.md and 02-assembly.md.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent

C_SIG, C_PWR, C_GND, C_MOT = "#1565C0", "#C62828", "#212121", "#EF6C00"

TEXT = {
    "en": {
        "title": "CPU Jet Engine - Wiring Overview",
        "subtitle": "ESP32-C3 SuperMini + DRV8871 + N30 motor   |   firmware jetengine-usb 1.1",
        "pc": "PC", "pc_sub": "USB power + serial\nengine_host.py",
        "mcu": "ESP32-C3 SuperMini", "mcu_sub": "3.3 V logic - USB-CDC 115200",
        "drv": "DRV8871", "drv_sub": "H-bridge - VM 6.5~45 V - 3.6 A",
        "motor": "N30 motor",
        "pwr": "12 V supply", "pwr_sub": "+12 V -> VM\n- -> GND",
        "sw": "Panel switch",
        "usb": "USB-C\n5 V + data",
        "gpio3": "GPIO3  PWM 20 kHz",
        "gpio4": "GPIO4 (internal pull-up)",
        "esp_gnd": "ESP32 GND",
        "drv_gnd": "DRV GND",
        "ilim": "ILIM 1.36 A",
        "vm": "VM +12 V",
        "bus": "GND bus: ESP32 GND / DRV8871 GND / 12 V -  all tied here",
        "notes": [
            "1  GPIO3 drives DRV8871 IN1 through a 1k resistor: 20 kHz PWM speed control. IN2 tied to GND -> one direction only.",
            "2  ILIM to GND through 47k: I_limit = 64 / 47(k) ~ 1.36 A, protects both motor and driver.",
            "3  GPIO4 has an internal pull-up and must be pulled to GND to RUN. Open = coast to a stop (fail-safe: stays still).",
            "4  12 V goes only to DRV8871 VM; the ESP32 is USB powered. The 12 V negative must still share GND with the ESP32.",
            "5  Add 100uF electrolytic + 0.1uF ceramic between VM and GND, close to the chip, to absorb commutation spikes.",
        ],
    },
    "zh": {
        "title": "喷气发动机模型 · 电路接线图",
        "subtitle": "ESP32-C3 SuperMini + DRV8871 + N30 电机   |   固件 jetengine-usb 1.1",
        "pc": "电脑", "pc_sub": "USB 供电+串口\nengine_host.py",
        "mcu": "ESP32-C3 SuperMini", "mcu_sub": "3.3V 逻辑 · USB-CDC 115200",
        "drv": "DRV8871", "drv_sub": "H 桥 · VM 6.5~45V · 3.6A",
        "motor": "N30 电机",
        "pwr": "12V 电源", "pwr_sub": "+12V → VM\n负极 → GND",
        "sw": "面板开关",
        "usb": "USB-C\n5V+数据",
        "gpio3": "GPIO3  PWM 20kHz",
        "gpio4": "GPIO4（内部上拉）",
        "esp_gnd": "ESP32 GND",
        "drv_gnd": "DRV GND",
        "ilim": "限流 1.36A",
        "vm": "VM +12V",
        "bus": "GND 母线：ESP32 GND / DRV8871 GND / 12V 负极 全部接这里",
        "notes": [
            "① GPIO3 经 1kΩ 接 DRV8871 IN1，20 kHz PWM 调速；IN2 固定接地 → 只走单方向",
            "② ILIM 经 47kΩ 接地：I_limit = 64 / 47(kΩ) ≈ 1.36 A，保护电机与驱动",
            "③ GPIO4 内部上拉，接 GND 才「允许转」；断开立即滑行停转（失效安全，宁可不动）",
            "④ 12V 只接 DRV8871 的 VM，ESP32 由 USB 供电；12V 负极与 ESP32 GND 必须连通",
            "⑤ 建议在 VM 与 GND 之间加 100µF 电解 + 0.1µF 陶瓷去耦，抑制电机换向尖峰",
        ],
    },
}


def pick_font(lang: str) -> None:
    if lang != "zh":
        plt.rcParams["font.family"] = "DejaVu Sans"
        return
    for cand in ("Noto Sans CJK SC", "Noto Serif CJK SC"):
        path = subprocess.check_output(["fc-match", "-f", "%{file}", cand]).decode().strip()
        if path:
            fm.fontManager.addfont(path)
            plt.rcParams["font.family"] = fm.FontProperties(fname=path).get_name()
            return
    raise SystemExit("No CJK font found; install fonts-noto-cjk for --lang zh")


def draw(lang: str) -> pathlib.Path:
    t = TEXT[lang]
    pick_font(lang)
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def box(x, y, w, h, title, sub="", fc="#E3F2FD", ec=C_SIG, fs=15):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.09",
                                    fc=fc, ec=ec, lw=2.2, zorder=2))
        ax.text(x + w / 2, y + h * (0.62 if sub else 0.5), title, ha="center",
                va="center", fontsize=fs, weight="bold", zorder=3)
        if sub:
            ax.text(x + w / 2, y + h * 0.24, sub, ha="center", va="center",
                    fontsize=10, color="#37474F", zorder=3)

    def line(pts, color=C_SIG, lw=2.4, arrow=True):
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            if i == len(pts) - 2 and arrow:
                ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                            arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                            shrinkA=0, shrinkB=0), zorder=1)
            else:
                ax.plot([x1, x2], [y1, y2], color=color, lw=lw, zorder=1,
                        solid_capstyle="round")

    def lab(x, y, text, color=C_SIG, fs=10, ha="center", bold=True):
        ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=color,
                weight="bold" if bold else "normal", zorder=5,
                bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.95))

    def gnd(x, y):
        ax.plot([x - 0.26, x + 0.26], [y, y], color=C_GND, lw=2.6, zorder=3)
        ax.plot([x - 0.17, x + 0.17], [y - 0.11, y - 0.11], color=C_GND, lw=2.2, zorder=3)
        ax.plot([x - 0.08, x + 0.08], [y - 0.22, y - 0.22], color=C_GND, lw=2.0, zorder=3)

    def res(x, y, w, h, text, vertical=False):
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="#FFF9C4",
                               ec="#F9A825", lw=2, zorder=3))
        if vertical:
            ax.text(x + 0.30, y, text, ha="left", va="center", fontsize=10,
                    color="#F57F17", weight="bold", zorder=5)
        else:
            ax.text(x, y + 0.36, text, ha="center", va="center", fontsize=10,
                    color="#F57F17", weight="bold", zorder=5)

    # ---- blocks ----
    box(0.3, 6.3, 2.4, 1.9, t["pc"], t["pc_sub"], fc="#ECEFF1", ec="#546E7A", fs=14)
    box(4.0, 5.3, 3.6, 3.7, t["mcu"], t["mcu_sub"])
    box(9.0, 6.0, 3.2, 2.5, t["drv"], t["drv_sub"], fc="#E8F5E9", ec="#2E7D32")
    box(13.4, 6.5, 2.4, 1.5, t["motor"], "", fc="#FFF3E0", ec=C_MOT)
    box(10.2, 3.5, 2.5, 1.35, t["pwr"], t["pwr_sub"], fc="#FFEBEE", ec=C_PWR, fs=12)
    box(4.2, 3.4, 2.3, 1.2, t["sw"], "", fc="#FFF8E1", ec="#F9A825", fs=12)

    # ---- DRV8871 pin names ----
    for py, nm in ((8.05, "IN1"), (7.35, "IN2")):
        ax.text(9.12, py, nm, ha="left", va="center", fontsize=9.5,
                color="#1B5E20", weight="bold", zorder=6)
    ax.text(9.30, 6.14, "ILIM", ha="left", va="center", fontsize=10,
            color="#1B5E20", weight="bold", zorder=6)
    ax.text(10.95, 6.14, "VM", ha="left", va="center", fontsize=10,
            color="#1B5E20", weight="bold", zorder=6)
    for py, nm in ((7.95, "OUT1"), (6.75, "OUT2")):
        ax.text(12.08, py, nm, ha="right", va="center", fontsize=9.5,
                color="#1B5E20", weight="bold", zorder=6)

    # ---- wires ----
    line([(2.7, 7.25), (4.0, 7.25)], C_SIG)
    lab(3.35, 7.62, t["usb"], fs=9.5)

    line([(7.6, 8.05), (9.0, 8.05)], C_SIG)
    res(8.3, 8.05, 0.62, 0.30, "1k")
    lab(7.0, 8.55, t["gpio3"], fs=10.5)

    line([(12.2, 7.95), (13.4, 7.95)], C_MOT)
    line([(12.2, 6.75), (13.4, 6.75)], C_MOT)
    lab(12.8, 8.28, "OUT1", C_MOT, fs=9.5)
    lab(12.8, 6.42, "OUT2", C_MOT, fs=9.5)

    line([(9.0, 7.35), (8.5, 7.35), (8.5, 2.85)], C_GND, lw=2.2)

    line([(9.5, 6.0), (9.5, 4.6)], C_GND, lw=2.2, arrow=False)
    res(9.5, 4.35, 0.30, 0.55, "47k", vertical=True)
    line([(9.5, 4.07), (9.5, 2.85)], C_GND, lw=2.2, arrow=False)
    lab(10.38, 4.30, t["ilim"], C_GND, fs=9.5)

    line([(11.2, 6.0), (11.2, 4.7)], C_PWR)
    lab(11.75, 5.35, t["vm"], C_PWR, fs=10)

    line([(5.35, 5.3), (5.35, 4.6)], C_SIG)
    lab(6.65, 5.05, t["gpio4"], fs=10)

    line([(6.5, 4.0), (6.9, 4.0), (6.9, 2.85)], C_GND, lw=2.2, arrow=False)

    line([(7.4, 5.3), (7.4, 2.85)], C_GND, lw=2.2, arrow=False)
    ax.text(7.55, 4.55, t["esp_gnd"], ha="left", va="center", fontsize=9,
            color=C_GND, weight="bold", zorder=6)

    line([(9.85, 6.0), (9.85, 2.85)], C_GND, lw=2.2, arrow=False)
    ax.text(9.95, 5.05, t["drv_gnd"], ha="left", va="center", fontsize=9,
            color=C_GND, weight="bold", zorder=6)

    ax.plot([6.9, 11.2], [2.85, 2.85], color=C_GND, lw=2.6, zorder=1)
    line([(11.2, 2.85), (11.2, 3.5)], C_GND, lw=2.2, arrow=False)
    gnd(8.3, 2.85)
    lab(9.2, 2.38, t["bus"], C_GND, fs=10)

    # ---- title ----
    ax.text(8.0, 9.62, t["title"], ha="center", fontsize=22, weight="bold", color="#0D47A1")
    ax.text(8.0, 9.12, t["subtitle"], ha="center", fontsize=12, color="#455A64")

    for i, note in enumerate(t["notes"]):
        ax.text(0.45, 1.72 - i * 0.34, note, ha="left", va="center",
                fontsize=10.3, color="#263238")

    plt.tight_layout()
    out = HERE / "docs" / "assets" / (
        "wiring-diagram.png" if lang == "en" else "wiring-diagram.zh-CN.png")
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lang", choices=("en", "zh"), default="en")
    print("saved:", draw(ap.parse_args().lang))
