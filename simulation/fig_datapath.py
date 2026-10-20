"""Passenger-information data path (Fig. 4), drawn on a fixed grid."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "figures", "fig_datapath.png")
plt.rcParams.update({"font.family": "DejaVu Sans"})
fig, ax = plt.subplots(figsize=(10.5, 5.6), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 56)
ax.axis("off")


def cluster(x, y, w, h, title, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec="#999999", lw=1))
    ax.text(x + 1.2, y + h - 1.3, title, ha="left", va="top", fontsize=10.5, fontweight="bold", color="#333333")


def box(cx, cy, w, h, title, sub, bold_edge=False):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.9",
                                fc="white", ec="#AD1457" if bold_edge else "#333333", lw=2.2 if bold_edge else 1))
    ax.text(cx, cy + (1.1 if sub else 0), title, ha="center", va="center", fontsize=9.5, fontweight="bold")
    if sub:
        ax.text(cx, cy - 1.6, sub, ha="center", va="center", fontsize=7.6, color="#333333", linespacing=1.15)
    return (cx, cy, w, h)


def arrow(p, q, dashed=False, label=None, lpos=None, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=11, lw=1.1, color="#444444",
                                 linestyle="--" if dashed else "-", connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text(*lpos, label, fontsize=7.8, color="#444444", ha="center", va="center",
                bbox=dict(fc="white", ec="none", pad=0.5))


L = lambda b: (b[0] - b[2] / 2, b[1])
R = lambda b: (b[0] + b[2] / 2, b[1])
T = lambda b: (b[0], b[1] + b[3] / 2)
B = lambda b: (b[0], b[1] - b[3] / 2)

cluster(1, 38, 98, 17, "On the bus", "#F2F2F2")
s = box(13, 46.8, 23, 6.4, "Seat sensors", "FSR + DS18B20, one pair per seat")
g = box(13, 40.3, 23, 5.6, "Position source", "GNSS / AIS-140 tracker")
a = box(46, 43.5, 26, 8, "Domain A (ESP32)", "debounce, temperature band\nEMPTY / OBJECT / OCCUPIED")
b = box(81, 43.5, 26, 8, "Domain B (edge buffer)", "seat summary every 10 s\nand on every door close")
arrow(R(s), (a[0] - a[2] / 2, 45))
arrow(R(g), (a[0] - a[2] / 2, 42))
arrow(R(a), L(b))

cluster(1, 20, 98, 15, "Links (chosen automatically)", "#FAFAFA")
p = box(22, 26, 24, 7, "4G / Wi-Fi (primary)", "MQTT, about 200 bytes")
m = box(50, 26, 24, 7, "GSM fallback", "SMS summary every 30 s")
q = box(78, 26, 24, 7, "No link", "queue on the bus, replay later")
for t in (p, m, q):
    arrow(B(b), T(t), rad=0.0)

cluster(1, 1, 64, 17, "Control centre (Domain C)", "#E6E6E6")
cluster(67, 1, 32, 17, "At the stop", "#F2F2F2")
st = box(12, 8, 18, 7, "Latest state", "one record per bus")
e = box(33, 8, 18, 7, "ETA engine", "recent segment\ntravel times")
bb = box(54, 8, 18, 7, "Stop board", "next 4 buses,\nrebuilt every 10 s")
tv = box(83, 10.5, 28, 7, "TV display", "route, minutes, free seats\n(~ when data > 60 s old)", bold_edge=True)
ap = box(83, 4.2, 28, 4, "App / SMS query", "")
arrow(B(p), (st[0] - 3, st[1] + st[3] / 2))
arrow(B(m), (st[0] + 2, st[1] + st[3] / 2), rad=0.0)
arrow(B(q), (st[0] + 6, st[1] + st[3] / 2), dashed=True, label="on reconnect", lpos=(52, 17.6))
arrow(R(st), L(e))
arrow(R(e), L(bb))
arrow((bb[0] + bb[2] / 2, 9.5), L(tv))
arrow((bb[0] + bb[2] / 2, 6.5), L(ap))

fig.savefig(OUT, bbox_inches="tight", pad_inches=0.05)
print("saved", OUT)
