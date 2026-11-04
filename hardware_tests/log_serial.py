import argparse
import csv
import sys
import threading
import time

import serial
from serial.tools import list_ports

HEADER = "ms,raw,median,ema,baseline,net,state,transitions,t_a,t_b,ax,ay,az".split(",")


def pick_port(given):
    if given:
        return given
    ports = list(list_ports.comports())
    if not ports:
        sys.exit("No serial port found. Plug in the ESP32 and pass --port.")
    for p in ports:
        desc = (p.description or "") + " " + (p.manufacturer or "")
        if any(k in desc for k in ("CP210", "CH340", "CH910", "USB", "UART", "Silicon")):
            return p.device
    return ports[0].device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    port = pick_port(args.port)
    ser = serial.Serial(port, args.baud, timeout=1)
    print(f"Logging {port} -> {args.out}")
    print("Type a label and press Enter (for example: 20kg, sit, bag_sun, empty). Type q to stop.")

    state = {"label": "start", "run": True, "rows": 0}
    lock = threading.Lock()
    f = open(args.out, "w", newline="")
    w = csv.writer(f)
    header_written = False

    def reader():
        nonlocal header_written
        while state["run"]:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("#"):
                print(line)
                continue
            parts = line.split(",")
            if parts[0] == "ms":
                if not header_written:
                    w.writerow(["host_time", "label"] + parts)
                    header_written = True
                continue
            if not header_written:
                if len(parts) != len(HEADER) or not parts[0].isdigit():
                    continue
                w.writerow(["host_time", "label"] + HEADER)
                header_written = True
            with lock:
                w.writerow([f"{time.time():.3f}", state["label"]] + parts)
                state["rows"] += 1
                if state["rows"] % 50 == 0:
                    f.flush()
                    print(f"\r{state['rows']} rows  label={state['label']}  last={line[:70]}   ", end="", flush=True)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        while True:
            lab = input().strip()
            if lab.lower() == "q":
                break
            if lab:
                with lock:
                    state["label"] = lab
                print(f"\nlabel -> {lab}")
    except (KeyboardInterrupt, EOFError):
        pass
    state["run"] = False
    time.sleep(1.2)
    f.close()
    ser.close()
    print(f"\nSaved {state['rows']} rows to {args.out}")


if __name__ == "__main__":
    main()
