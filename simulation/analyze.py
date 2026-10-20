import glob
import json
import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "..", "figures")
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#8a8984", "axes.linewidth": 0.8,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "figure.dpi": 200, "savefig.bbox": "tight", "legend.frameon": False,
})


def load(scenario):
    out = []
    for f in sorted(glob.glob(os.path.join(RES, f"result_{scenario}_*.json"))):
        out.append(json.load(open(f)))
    return out


def ci95(vals):
    v = np.array(vals, dtype=float)
    if len(v) < 2:
        return float(v.mean()), 0.0
    return float(v.mean()), float(1.96 * v.std(ddof=1) / np.sqrt(len(v)))


def main():
    A, BR, BO = load("A"), load("B_real"), load("B_oracle")
    allruns = A + BR + BO
    M = {"runs": {"A": len(A), "B_real": len(BR), "B_oracle": len(BO)}}

    arr = [a for r in allruns for a in r["arrivals"]]
    M["arrivals_n"] = len(arr)
    loads_by_stop = defaultdict(list)
    for r in A:
        for a in r["arrivals"]:
            loads_by_stop[a["stop"]].append(a["load"])
    M["load_by_stop_mean"] = [float(np.mean(loads_by_stop[s])) for s in range(20)]
    M["load_by_stop_p90"] = [float(np.percentile(loads_by_stop[s], 90)) for s in range(20)]
    M["share_arrivals_no_free_seat"] = float(np.mean([a["gt_free"] == 0 for r in A for a in r["arrivals"]]))

    seat = {}
    for c in ("fallback", "primary_only", "oracle"):
        pairs = [(a["gt_free"], a[f"shown_{c}"]) for a in arr]
        miss = sum(1 for g, s in pairs if s is None)
        ok = [(g, s) for g, s in pairs if s is not None]
        err = np.array([s - g for g, s in ok])
        seat[c] = {
            "n": len(pairs), "missing": miss, "mae": float(np.abs(err).mean()), "exact": float((err == 0).mean()),
            "within1": float((np.abs(err) <= 1).mean()), "within2": float((np.abs(err) <= 2).mean()),
            "yesno": float(np.mean([(g > 0) == (s > 0) for g, s in ok])),
            "false_seat": float(np.mean([(g == 0) and (s > 0) for g, s in ok])),
            "false_full": float(np.mean([(g > 0) and (s == 0) for g, s in ok])),
            "bias": float(err.mean()), "hist": np.bincount(np.clip(err + 5, 0, 10).astype(int), minlength=11).tolist(),
        }
    M["seat_display"] = seat

    hist = np.zeros(21)
    for r in allruns:
        h = np.array(r["free_err_hist"])
        hist[:len(h)] += h
    M["onboard_free_err"] = {"exact": float(hist[10] / hist.sum()), "within1": float(hist[9:12].sum() / hist.sum()),
                             "within2": float(hist[8:13].sum() / hist.sum()), "samples": int(hist.sum())}

    bins = [(0, 120), (120, 300), (300, 600), (600, 1200)]
    eta = {}
    for c in ("fallback", "primary_only", "oracle"):
        e = np.array([x for r in allruns for x in r["eta_err"][c]])
        eta[c] = []
        for lo, hi in bins:
            m = (e[:, 0] >= lo) & (e[:, 0] < hi)
            eta[c].append({"lo": lo, "hi": hi, "n": int(m.sum()), "mae_s": float(np.abs(e[m, 1]).mean()),
                           "bias_s": float(e[m, 1].mean()), "p90_abs_s": float(np.percentile(np.abs(e[m, 1]), 90))})
    M["eta"] = eta

    st = {}
    for c in ("fallback", "primary_only"):
        v = np.array([x for r in allruns for x in r["staleness"][c]])
        st[c] = {"p50": float(np.percentile(v, 50)), "p95": float(np.percentile(v, 95)), "p99": float(np.percentile(v, 99)),
                 "max": float(v.max()), "over60": float((v > 60).mean()), "over30": float((v > 30).mean())}
    M["staleness"] = st

    conf = defaultdict(lambda: {"fixed": np.zeros((2, 2)), "env": np.zeros((2, 2))})
    for r in allruns:
        for amb, d in r["conf"].items():
            for k in ("fixed", "env"):
                conf[amb][k] += np.array(d[k])
    temp = {}
    for amb in sorted(conf, key=float):
        temp[amb] = {}
        for k in ("fixed", "env"):
            m = conf[amb][k]
            temp[amb][k] = {"person_as_object": float(m[0, 1] / max(1, m[0].sum())),
                            "object_as_person": float(m[1, 0] / max(1, m[1].sum())),
                            "n_person": int(m[0].sum()), "n_object": int(m[1].sum())}
    M["temperature"] = temp

    def outcome(runs):
        o = {}
        o["seekers_seated_at_board"] = ci95([r["seekers_seated_at_board"] / r["seekers"] for r in runs])
        o["all_seated_at_board"] = ci95([r["all_seated_at_board"] / r["n_served"] for r in runs])
        o["seeker_mean_wait_min"] = ci95([np.mean(r["seeker_wait_s"]) / 60 for r in runs])
        o["all_mean_wait_min"] = ci95([np.mean(r["all_wait_s"]) / 60 for r in runs])
        o["seeker_seat_time_share"] = ci95([np.mean(r["seeker_seat_share"]) for r in runs])
        o["skippers_share_of_seekers"] = ci95([r["skippers"] / r["seekers"] for r in runs])
        o["left_behind_events"] = ci95([r["left_behind_events"] for r in runs])
        o["passengers"] = ci95([r["n_served"] for r in runs])
        return o
    M["outcomes"] = {"A": outcome(A), "B_real": outcome(BR), "B_oracle": outcome(BO)}
    paired = []
    for a in A:
        for b in BR:
            if a["seed"] == b["seed"]:
                paired.append((b["seekers_seated_at_board"] / b["seekers"]) - (a["seekers_seated_at_board"] / a["seekers"]))
    M["paired_seated_gain_B_real_minus_A"] = ci95(paired)
    pw = []
    for a in A:
        for b in BR:
            if a["seed"] == b["seed"]:
                pw.append(np.mean(b["seeker_wait_s"]) / 60 - np.mean(a["seeker_wait_s"]) / 60)
    M["paired_seeker_wait_delta_min"] = ci95(pw)

    fares = defaultdict(list)
    for r in A:
        for name, km, base, amt, size in r["fares"]:
            fares[name].append((km, base, amt, size))
    fs = {}
    for name, rows in fares.items():
        a = np.array(rows)
        fs[name] = {"records": len(rows), "mean_base": float(a[:, 1].mean()), "mean_paid": float(a[:, 2].mean()),
                    "record_bytes_mean": float(a[:, 3].mean()), "zero_fare_records": int((a[:, 2] == 0).sum())}
    M["fares"] = fs

    msgs = [m for r in allruns for m in (r.get("msgs") or [])]
    if msgs:
        hours = sum(m["seconds"] for m in msgs) / 3600
        M["messages"] = {"bus_hours": hours,
                         "primary_per_bus_hour": sum(m["primary"] for m in msgs) / hours,
                         "sms_per_bus_hour": sum(m["sms"] for m in msgs) / hours,
                         "kb_primary_per_bus_hour": sum(m["bytes_primary"] for m in msgs) / hours / 1024,
                         "buffered_share": sum(m["buffered"] for m in msgs) / max(1, sum(m["primary"] + m["buffered"] for m in msgs)),
                         "mean_primary_bytes": sum(m["bytes_primary"] for m in msgs) / max(1, sum(m["primary"] for m in msgs))}
    M["wall_s_mean"] = float(np.mean([r["wall_s"] for r in allruns]))
    json.dump(M, open(os.path.join(RES, "metrics.json"), "w"), indent=1)
    figures(M, A, BR, BO, allruns)
    return M


def figures(M, A, BR, BO, allruns):
    x = np.arange(1, 21)
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.plot(x, M["load_by_stop_mean"], color=S1, lw=2, marker="o", ms=4, label="Mean on-board load")
    ax.plot(x, M["load_by_stop_p90"], color=S2, lw=2, marker="s", ms=4, label="90th percentile")
    ax.axhline(44, color=INK2, lw=1.2, ls="--")
    ax.text(20.3, 44, "44 seats", va="center", color=INK2, fontsize=9)
    ax.axhline(69, color=INK2, lw=1.0, ls=":")
    ax.text(20.3, 69, "44 + 25 standing", va="center", color=INK2, fontsize=9)
    ax.set_xlabel("Stop on corridor (bus arriving, before alighting)")
    ax.set_ylabel("Passengers on board")
    ax.set_xticks(x)
    ax.set_xlim(0.5, 20.5)
    ax.set_ylim(0, 80)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    fig.savefig(os.path.join(FIG, "fig_load_profile.png"))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    h = np.array(M["seat_display"]["fallback"]["hist"], dtype=float)
    h = h / h.sum() * 100
    xs = np.arange(-5, 6)
    ax.bar(xs, h, color=S1, width=0.7)
    for xi, hi in zip(xs, h):
        if hi >= 0.5:
            ax.text(xi, hi + 1.5, f"{hi:.1f}%", ha="center", fontsize=8, color=INK)
    ax.set_xlabel("Displayed free seats minus true free seats when the bus reaches the stop")
    ax.set_ylabel("Share of arrivals (%)")
    ax.set_xticks(xs)
    ax.set_ylim(0, max(h) * 1.18)
    fig.savefig(os.path.join(FIG, "fig_seat_error.png"))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    labels = ["0-2 min", "2-5 min", "5-10 min", "10-20 min"]
    w = 0.38
    for i, (c, col, lab) in enumerate((("fallback", S1, "With GSM/SMS fallback"), ("primary_only", S2, "Primary link only"))):
        vals = [b["mae_s"] for b in M["eta"][c]]
        pos = np.arange(4) + (i - 0.5) * w
        ax.bar(pos, vals, width=w - 0.04, color=col, label=lab)
        for p, v in zip(pos, vals):
            ax.text(p, v + 2, f"{v:.0f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(np.arange(4))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Prediction horizon (actual time to arrival)")
    ax.set_ylabel("Mean absolute ETA error (s)")
    ax.legend(loc="upper left")
    fig.savefig(os.path.join(FIG, "fig_eta_error.png"))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    for c, col, lab, ls in (("fallback", S1, "With GSM/SMS fallback", "-"), ("primary_only", S2, "Primary link only", "--")):
        v = np.sort(np.array([x for r in allruns for x in r["staleness"][c]]))
        y = np.arange(1, len(v) + 1) / len(v) * 100
        idx = np.linspace(0, len(v) - 1, 600).astype(int)
        ax.plot(v[idx], y[idx], color=col, lw=2, ls=ls, label=lab)
    ax.axvline(60, color=INK2, lw=1, ls=":")
    ax.text(61, 50, "board marks rows\nolder than 60 s", fontsize=8, color=INK2)
    ax.set_xlim(0, 180)
    ax.set_xlabel("Age of the bus data behind a displayed row (s)")
    ax.set_ylabel("Cumulative share of rows (%)")
    ax.legend(loc="lower right")
    fig.savefig(os.path.join(FIG, "fig_staleness.png"))
    plt.close(fig)

    amb = sorted(M["temperature"], key=float)
    ta = [float(a) for a in amb]
    fig, axs = plt.subplots(1, 2, figsize=(6.6, 2.8), sharey=True)
    for ax, key, title in ((axs[0], "person_as_object", "Seated person read as OBJECT"), (axs[1], "object_as_person", "Bag read as OCCUPIED")):
        ax.plot(ta, [M["temperature"][a]["fixed"][key] * 100 for a in amb], color=S2, lw=2, marker="s", ms=5, label="Fixed 34-42 °C band")
        ax.plot(ta, [M["temperature"][a]["env"][key] * 100 for a in amb], color=S1, lw=2, marker="o", ms=5, label="Band set for environment (pressure-only from 32 °C)")
        ax.set_title(title, fontsize=10, color=INK)
        ax.set_xlabel("Cabin ambient temperature (°C)")
    axs[0].set_ylabel("Misclassified (%)")
    h, l = axs[1].get_legend_handles_labels()
    fig.subplots_adjust(bottom=0.3)
    fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=2, fontsize=9)
    fig.savefig(os.path.join(FIG, "fig_temperature.png"))
    plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(6.6, 2.8))
    names = [("A", "No display"), ("B_real", "Display"), ("B_oracle", "Display,\nperfect data")]
    cols = [INK2, S1, S3]
    for ax, key, ylab, scale in ((axs[0], "seekers_seated_at_board", "Seat-seekers seated at boarding (%)", 100),
                                 (axs[1], "seeker_mean_wait_min", "Seat-seekers' mean wait (min)", 1)):
        for i, (k, lab) in enumerate(names):
            m, c = M["outcomes"][k][key]
            ax.bar(i, m * scale, color=cols[i], width=0.6, yerr=c * scale, capsize=3, ecolor=INK)
            ax.text(i, m * scale + c * scale + (1.2 if scale == 100 else 0.08), f"{m*scale:.1f}", ha="center", fontsize=8)
        ax.set_xticks(range(3))
        ax.set_xticklabels([n[1] for n in names], fontsize=8)
        ax.set_ylabel(ylab, fontsize=9)
    axs[0].set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_outcomes.png"))
    plt.close(fig)

    import math, sys
    sys.path.insert(0, os.path.join(HERE, "..", "reference"))
    from transit_core import base_fare, slab_policy, stage_policy, per_km_policy, flat_policy
    pols = [("Distance slab (5/10/15)", slab_policy([(4, 5), (10, 10), (math.inf, 15)]), S1, "-"),
            ("Stage table (2 km stages)", stage_policy(2.0, [6, 8, 10, 12, 14, 16, 18]), S2, "--"),
            ("Per-km (Rs 1/km, min Rs 5)", per_km_policy(1.0, 5.0), S3, "-."),
            ("Flat (Rs 10)", flat_policy(10.0), INK2, ":")]
    d = np.linspace(0.05, 12, 600)
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for lab, p, col, ls in pols:
        ax.plot(d, [base_fare(p, x) for x in d], color=col, lw=2, ls=ls, label=lab, drawstyle="steps-post")
    ax.set_xlabel("Trip distance (km)")
    ax.set_ylabel("Fare (Rs)")
    ax.legend(loc="upper left", fontsize=8)
    fig.savefig(os.path.join(FIG, "fig_fares.png"))
    plt.close(fig)


if __name__ == "__main__":
    M = main()
    print(json.dumps({k: M[k] for k in ("runs", "seat_display", "eta", "staleness", "outcomes", "paired_seated_gain_B_real_minus_A", "paired_seeker_wait_delta_min", "messages", "onboard_free_err", "share_arrivals_no_free_seat")}, indent=1))
    print(json.dumps(M["temperature"], indent=1))
    print(json.dumps(M["fares"], indent=1))
