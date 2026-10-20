import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reference"))
from transit_core import base_fare, per_km_policy

FIG = os.path.join(HERE, "..", "figures")
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#8a8984", "xtick.color": INK2, "ytick.color": INK2, "figure.dpi": 200, "savefig.bbox": "tight"})

fig, ax = plt.subplots(figsize=(5.6, 3.0))
labels = ["Indexed INSERT\n(one trip record)", "Indexed SELECT\n(by rider ID)", "Paginated dashboard\nfetch (LIMIT 50)"]
vals = [3.19, 7.06, 78.74]
ax.bar(range(3), vals, color=S1, width=0.55)
for i, v in enumerate(vals):
    ax.text(i, v + 2, f"{v:.2f} µs", ha="center", fontsize=9, color=INK)
ax.set_xticks(range(3))
ax.set_xticklabels(labels, fontsize=8.5)
ax.set_ylabel("Mean time (µs)")
ax.set_ylim(0, 90)
ax.grid(axis="y", color=GRID, lw=0.6)
fig.savefig(os.path.join(FIG, "fig_storage.png"))
plt.close(fig)

fig, ax = plt.subplots(figsize=(5.6, 2.4))
cases = ["Bus full\n(30/30, 31st refused)", "Empty route\n(idle state)", "Rapid polling\n(15 entry/exit cycles)"]
ax.barh(range(3), [1, 1, 1], color=S3, height=0.6)
for i in range(3):
    ax.text(0.5, i, "PASS", ha="center", va="center", color="white", weight="bold")
ax.set_yticks(range(3))
ax.set_yticklabels(cases, fontsize=8.5)
ax.set_xticks([])
ax.spines["bottom"].set_visible(False)
fig.savefig(os.path.join(FIG, "fig_functional.png"))
plt.close(fig)

pol = per_km_policy(5.0, 2.0)
d = np.linspace(0, 5, 200)
fig, ax = plt.subplots(figsize=(5.6, 3.0))
ax.plot(d, [base_fare(pol, x) for x in d], color=S1, lw=2)
ax.axhline(2.0, color=INK2, lw=1, ls="--")
ax.axvline(0.4, color=INK2, lw=0.8, ls=":")
ax.text(0.45, 3.0, "break-even 0.4 km", fontsize=8, color=INK2)
ax.text(4.0, 2.6, "minimum fare ₹2.00", fontsize=8, color=INK2)
ax.set_xlabel("Trip distance (km)")
ax.set_ylabel("Fare (₹)")
ax.grid(color=GRID, lw=0.6)
fig.savefig(os.path.join(FIG, "fig_fare_perkm.png"))
plt.close(fig)
print("ok")
