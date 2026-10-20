import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "..", "figures")

r = json.load(open(os.path.join(HERE, "results", "result_B_real_1.json")))
board = r["snapshots"]["5400"]["8"]
rows = board["rows"]

fig = plt.figure(figsize=(6.4, 3.6), dpi=220)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 16)
ax.set_ylim(0, 9)
ax.axis("off")
ax.add_patch(FancyBboxPatch((0.2, 0.3), 15.6, 8.4, boxstyle="round,pad=0.05,rounding_size=0.25", fc="#202020", ec="#000000", lw=3))
ax.add_patch(Rectangle((0.55, 0.65), 14.9, 7.7, fc="#111111", ec="none"))
W, Y = "#f2f2f2", "#bdbdbd"
ax.text(0.9, 7.75, "Stop 9  |  Corridor Road (towards Terminal)", color=W, fontsize=13, weight="bold", va="center")
ax.text(15.1, 7.75, "15:30", color=Y, fontsize=12, va="center", ha="right")
ax.plot([0.9, 15.1], [7.2, 7.2], color="#555555", lw=1)
cols = [0.9, 3.0, 6.0, 9.3]
for x, h in zip(cols, ["Route", "Bus", "Arrives in", "Seats"]):
    ax.text(x, 6.7, h, color=Y, fontsize=10, va="center")
y = 5.8
for row in rows:
    ax.text(cols[0], y, row["route"], color=W, fontsize=15, weight="bold", va="center")
    ax.text(cols[1], y, "Bus " + str(int(row["bus"][3:])), color=W, fontsize=13, va="center")
    eta = "Due" if row["eta_min"] == 0 else f"{row['eta_min']} min"
    ax.text(cols[2], y, eta, color=W, fontsize=15, weight="bold", va="center")
    lab = row["label"]
    seats = f"{row['free_seats']} free" if row["free_seats"] > 0 else "Full"
    ax.text(cols[3], y, seats, color=W, fontsize=15, weight="bold", va="center")
    ax.text(cols[3] + 2.4, y, lab.title(), color=Y, fontsize=11, va="center")
    if row["approximate"]:
        ax.text(14.9, y, "~", color=Y, fontsize=14, va="center")
    ax.plot([0.9, 15.1], [y - 0.62, y - 0.62], color="#2c2c2c", lw=1)
    y -= 1.35
ax.text(0.9, 1.15, "Seat counts come from seat sensors on each bus. Standing room is not shown.", color=Y, fontsize=8.5, va="center")
ax.text(0.9, 0.82, "Rows marked ~ use bus data older than 60 s.", color=Y, fontsize=8.5, va="center")
fig.savefig(os.path.join(FIG, "fig_display.png"), dpi=220)
print(rows)
