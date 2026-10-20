import json
import os
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from stats import load

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "..", "figures")
VARS = [("base", "Base case"), ("seek40", "40% want a seat"), ("seek80", "80% want a seat"),
        ("tolhalf", "Tolerance halved"), ("demand80", "Demand -20%"), ("demand120", "Demand +20%"),
        ("outage3x", "Outages x3")]

rows = []
for k, lab in VARS:
    v = "main" if k == "base" else k
    a, b = load(v, "A"), load(v, "B_real")
    seeds = sorted(set(a) & set(b))
    if not seeds:
        continue
    rows.append((lab, [100 * (b[s]["seated"] - a[s]["seated"]) for s in seeds]))

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
for i, (lab, vals) in enumerate(rows):
    y = len(rows) - 1 - i
    m = st.mean(vals)
    ax.barh(y, m, height=0.55, color="#2a78d6" if i else "#1baf7a", alpha=0.35)
    ax.scatter(vals, [y] * len(vals), color="#2a78d6" if i else "#1baf7a", s=22, zorder=3)
    ax.text(m + 0.4, y + 0.3, f"{m:.1f}", va="center", fontsize=9)
ax.set_yticks(range(len(rows)))
ax.set_yticklabels([r[0] for r in rows][::-1])
ax.axvline(0, color="#444", lw=0.8)
ax.set_xlabel("Gain in seat seekers seated at boarding (percentage points)")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", color="#ddd", lw=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_sensitivity.png"))
print([(r[0], round(st.mean(r[1]), 2)) for r in rows])
