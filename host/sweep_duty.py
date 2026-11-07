#!/usr/bin/env python3
"""占空比扫档：逐档保持固定占空比，打印清晰的时间轴，人工判断哪几档能持续转。

用法: .venv/bin/python host/sweep_duty.py [端口]
每档 12 秒，档位 20/30/40/50/60/75。
"""
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
STEPS = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [20, 30, 40, 50, 60, 75]
HOLD = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0

sp = serial.Serial(PORT, 115200, timeout=0.05)
time.sleep(0.3)
sp.reset_input_buffer()
sp.write(b"E 1\n")          # 绕开开关
sp.flush()
time.sleep(0.2)

t0 = time.time()
print("=== 开始扫档（每档 12 秒），请记下哪几档能持续转 ===")
for duty in STEPS:
    start = time.time() - t0
    print(f"\n>>> [{start:5.1f}s → {start+HOLD:5.1f}s]  duty = {duty}%  <<<")
    end = time.time() + HOLD
    next_hb = 0.0
    while time.time() < end:
        if time.time() - t0 >= next_hb:
            next_hb += 0.5
            sp.write(f"T {duty}\n".encode())
            sp.flush()
        l = sp.readline().decode(errors="replace").strip()
        if l.startswith("#") and "refused" not in l and "kick" in l:
            print(f"      {time.time()-t0:5.1f}s {l}")

sp.write(b"S\nE 0\n")
sp.flush()
time.sleep(0.3)
sp.close()
print(f"\n=== 结束 ({time.time()-t0:.0f}s) ===")
for i, d in enumerate(STEPS):
    s = i * HOLD
    print(f"  {s:5.0f}–{s+HOLD:5.0f}s : {d}%")
