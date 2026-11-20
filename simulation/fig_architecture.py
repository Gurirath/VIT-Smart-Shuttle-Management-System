import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "figures", "fig_architecture.png")
INK, MID, LIGHT, ACCENT = "#1a1a1a", "#555555", "#f1f1f1", "#9c1d4f"
FS_T, FS_B = 7.4, 6.3

plt.rcParams.update({"font.family": "DejaVu Sans"})
fig, ax = plt.subplots(figsize=(7.2, 6.6), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")


def lane(y, h, title):
    ax.add_patch(FancyBboxPatch((0.4, y), 92.2, h, boxstyle="round,pad=0,rounding_size=1.0", fc=LIGHT, ec="#c4c4c4", lw=0.7))
    ax.text(2.6, y + h / 2, title, fontsize=6.4, fontweight="bold", color=MID, va="center", ha="center", rotation=90)


def block(x, y, w, h, num, title, lines, accent=False):
    ec = ACCENT if accent else INK
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8", fc="white", ec=ec, lw=1.5 if accent else 0.8))
    ax.text(x + 1.0, y + h - 1.1, num, fontsize=7.2, fontweight="bold", color="white", va="top", ha="left",
            bbox=dict(boxstyle="circle,pad=0.16", fc=ec, ec="none"))
    ax.text(x + 4.6, y + h - 1.15, title, fontsize=FS_T, fontweight="bold", color=INK, va="top")
    if lines:
        ax.text(x + 1.3, y + h - 4.9, "\n".join(lines), fontsize=FS_B, color=INK, va="top", linespacing=1.42)


def arrow(p, q, ls="-", color=INK, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=8, lw=0.9, color=color, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))


X1, X2, X3, W = 5.2, 34.4, 63.6, 27.4

lane(71.5, 28, "BUS: ESP32 (TIER A)")
block(X1, 73, W, 25, "1", "Sensing", ["FSR under each of 44 seats", "DS18B20 seat probes on four", "zone buses, 11 seats each", "cabin-air probe on own bus",
                                       "GNSS or AIS-140 position", "door and motion switches", "ticket, card or face token"])
block(X2, 73, W, 25, "2", "Conditioning", ["pressure: 10 Hz, median of 5,", "EMA α = 0.25, hysteresis", "1,200 / 1,000 counts", "ΔT = T_seat − T_cabin",
                                            "probe range check per bus", "NMEA parse, route progress", "stationary: < 3 m, < 0.5 m/s"])
block(X3, 73, W, 25, "3", "Classify and gate", ["EMPTY / OBJECT / OCCUPIED", "flags BLIND, PROBE_FAULT", "boarding only when stationary", "and door open",
                                                 "< 50 ms, needs no network", "sends state changes only"])
arrow((X1 + W, 85.5), (X2, 85.5))
arrow((X2 + W, 85.5), (X3, 85.5))

lane(53, 17, "EDGE (TIER B)")
block(X1, 54.5, 3 * W + 2 * (X2 - X1 - W), 14, "4", "Seat summary, queue and link manager",
      ["about 200 bytes every 10 s and at each door close; per-trip batch and billing-event queue",
       "4G or Wi-Fi: MQTT  |  GSM only: SMS on door close, ≥ 2 free seats changed, full / not full, or 300 s",
       "no link: hold in queue and replay on reconnect"])
arrow((X3 + W / 2, 73), (X3 + W / 2, 68.5))

lane(15, 36.5, "CONTROL CENTRE (TIER C)")
block(X1, 33, W, 17, "5", "Context checks", ["seat state vs boarding record", "entry / exit pairing", "ticket token or member lookup", "GNSS-jump fare check", "MQTT log vs SMS / queue log"])
block(X2, 33, W, 17, "6", "Severity decision", ["T1: log and keep monitoring", "T2: notify control room", "T3: alert and call maintenance"])
block(X1, 16.5, W, 14.5, "7", "Fares and ETA", ["slab, stage, per-km or flat", "ETA from recent segment", "travel times, per route"])
block(X3, 16.5, W, 33.5, "9", "Storage, analytics", ["event and vehicle-log archive", "trip and billing dashboard", "seat load by route, segment", "and hour", "dispatch tuning",
                                                        "season thresholds and band", "role-based access"])
arrow((X1 + W / 2, 54.5), (X1 + W / 2, 50))
arrow((X1 + W, 41.5), (X2, 41.5))
arrow((X2 + W, 41.5), (X3, 41.5))
arrow((X1 + W, 23.5), (X3, 23.5))
arrow((X1 + W / 2, 33), (X1 + W / 2, 31))

block(X1, 0.5, W + 12, 13.5, "8", "Stop board for riders", ["next 4 buses: route, minutes, free seats", "no seat: \"0 seats (standing only)\"", "~ when data are over 60 s old"], accent=True)
block(X2 + 12, 0.5, W - 5, 13.5, "!", "Staff alerts", ["control room,", "maintenance or", "billing office"])
arrow((X1 + W / 2, 16.5), (X1 + W / 2, 14))
arrow((X2 + W / 2 + 7, 33), (X2 + W / 2 + 7, 14))
ax.text(X3 + W / 2 + 4, 7.2, "no camera on the bus\nper-seat data stay on it\nhashed ticket token\nTLS MQTT when deployed",
        fontsize=5.9, color=MID, ha="center", va="center", style="italic", linespacing=1.35)

ax.plot([X3 + W, 96.2, 96.2], [33.25, 33.25, 85.5], color=MID, lw=0.9, ls=(0, (3, 2)))
arrow((96.2, 85.5), (X3 + W, 85.5), ls="-", color=MID)
ax.text(97.9, 59, "feedback: thresholds, band, dispatch settings", rotation=90, fontsize=5.9, color=MID, va="center", ha="center")
fig.savefig(OUT, bbox_inches="tight", pad_inches=0.04)
print("saved", OUT)
