import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from stats import BETA_SEAT, BETA_WAIT

HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, "results", "stats.json")))["grid"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.3), dpi=200)
for ax, key, scale, title, fmt in ((axes[0], "seated_gain", 100, "Gain in seat seekers seated (pp)", "{:.1f}"),
                                   (axes[1], "wait_delta_min", 1, "Extra wait for seat seekers (min)", "{:.2f}")):
    m = np.full((len(BETA_WAIT), len(BETA_SEAT)), np.nan)
    for i, bw in enumerate(BETA_WAIT):
        for j, bs in enumerate(BETA_SEAT):
            g = G.get(f"bw{bw}_bs{bs}")
            if g:
                m[i, j] = g[key] * scale
    im = ax.imshow(m, cmap="Blues", aspect="auto", origin="upper")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            if not np.isnan(m[i, j]):
                v = m[i, j]
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=7.5,
                        color="white" if v > np.nanmax(m) * 0.6 else "#111111")
    ax.add_patch(plt.Rectangle((BETA_SEAT.index(2.0) - 0.5, BETA_WAIT.index(-0.35) - 0.5), 1, 1, fill=False, lw=1.6, ec="#eb6834"))
    ax.set_xticks(range(len(BETA_SEAT)))
    ax.set_xticklabels([f"{b:g}" for b in BETA_SEAT])
    ax.set_yticks(range(len(BETA_WAIT)))
    ax.set_yticklabels([f"{b:g}" for b in BETA_WAIT])
    ax.set_xlabel("β_seat")
    ax.set_ylabel("β_wait (per min)")
    ax.set_title(title, fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "..", "figures", "fig_beta_grid.png"))
print("ok")
