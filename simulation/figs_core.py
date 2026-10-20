import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reference"))
from transit_core import SeatConfig, classify_seat, configure_for_environment, EMPTY, OBJECT, OCCUPIED

FIG = os.path.join(HERE, "..", "figures")
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#8a8984", "xtick.color": INK2, "ytick.color": INK2, "figure.dpi": 200, "savefig.bbox": "tight"})

code = {EMPTY: 0, OBJECT: 1, OCCUPIED: 2}
cmap = ListedColormap(["#e9e8e4", "#f6c9ad", "#a9d6c3"])
p = np.linspace(0, 4095, 300)
t = np.linspace(0, 50, 300)
fig, axs = plt.subplots(1, 2, figsize=(6.8, 3.0), sharey=True)
for ax, cfg, title in ((axs[0], SeatConfig().validate(), "Default band 34-42 °C"),
                       (axs[1], configure_for_environment(SeatConfig(), 26.0), "Band set for a 26 °C cabin (28-42 °C)")):
    z = np.array([[code[classify_seat(pp, tt, cfg)] for pp in p] for tt in t])
    ax.imshow(z, origin="lower", extent=[0, 4095, 0, 50], aspect="auto", cmap=cmap, vmin=0, vmax=2)
    ax.axvline(cfg.pressure_threshold, color=INK2, lw=0.8, ls="--")
    for y in (cfg.temp_min_c, cfg.temp_max_c):
        ax.axhline(y, color=INK2, lw=0.8, ls="--")
    ax.text(500, 25, "EMPTY", ha="center", fontsize=9, weight="bold", color=INK)
    ax.text(2700, (cfg.temp_min_c + cfg.temp_max_c) / 2, "OCCUPIED", ha="center", va="center", fontsize=9, weight="bold", color=INK)
    ax.text(2700, cfg.temp_min_c / 2, "OBJECT", ha="center", va="center", fontsize=9, weight="bold", color=INK)
    ax.set_title(title, fontsize=9.5, color=INK)
    ax.set_xlabel("Pressure reading (ADC counts)")
axs[0].set_ylabel("Seat temperature (°C)")
fig.savefig(os.path.join(FIG, "fig_regions.png"))
plt.close(fig)

B = json.load(open(os.path.join(HERE, "results", "bench.json")))["us_per_call"]
items = sorted(B.items(), key=lambda kv: kv[1])
fig, ax = plt.subplots(figsize=(6.6, 4.4))
names = [k for k, _ in items]
vals = [v for _, v in items]
cols = [S2 if k.startswith("FULL") else S1 for k in names]
ax.barh(range(len(vals)), vals, color=cols, height=0.62)
for i, v in enumerate(vals):
    ax.text(v * 1.08, i, f"{v:.2f} µs" if v < 10 else f"{v:.1f} µs", va="center", fontsize=7.5, color=INK)
ax.set_yticks(range(len(vals)))
ax.set_yticklabels(names, fontsize=7.5)
ax.set_xscale("log")
ax.set_xlim(min(vals) * 0.6, max(vals) * 4)
ax.set_xlabel("Mean time per call (µs, log scale)")
ax.grid(axis="x", color=GRID, lw=0.6)
fig.savefig(os.path.join(FIG, "fig_response_times.png"))
plt.close(fig)
print("ok")
