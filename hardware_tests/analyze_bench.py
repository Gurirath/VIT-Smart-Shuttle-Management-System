"""Turns the seat_logger CSVs into the numbers and figures for Section 4 (physical sensor characterization).

Usage: python analyze_bench.py <folder with CSVs> <output folder> [--simulated]
Files are matched by test name anywhere in the file name (test0_noise ... test6_ride).
"""
import argparse
import csv
import glob
import json
import math
import os
import re
import statistics as st
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reference"))
from transit_core import DifferentialSeatClassifier, RawThreshold, ThermalConfig

BLUE, ORANGE, GREEN, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#666666"
TESTS = ["test0_noise", "test1_calibration", "test2_creep", "test3_posture", "test4_thermal_room",
         "test5_thermal_hotcar", "test6_ride"]


def num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def load(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({k: (r[k] if k == "label" else num(r[k])) for k in r})
    return rows


def find(folder):
    out = {}
    for t in TESTS:
        hits = sorted(glob.glob(os.path.join(folder, f"*{t}*.csv")))
        if hits:
            out[t] = hits[0]
    return out


def steady(rows, label, key="raw", tail=0.5):
    vals = [r[key] for r in rows if r["label"] == label and r[key] is not None]
    if not vals:
        return None
    return st.median(vals[int(len(vals) * (1 - tail)):])


def stamp(ax, simulated):
    if simulated:
        ax.text(0.5, 0.5, "SIMULATED DATA", transform=ax.transAxes, ha="center", va="center",
                fontsize=22, color="#cc0000", alpha=0.18, rotation=20)


def calibration(rows, out, simulated):
    rounds = sorted({m.group(1) for r in rows for m in [re.match(r"(r\d+)_", r["label"] or "")] if m}) or [""]
    pts = {"up": {}, "down": {}, "person": {}}
    for rd in rounds:
        pre = f"{rd}_" if rd else ""
        for lab in {r["label"] for r in rows if (r["label"] or "").startswith(pre)}:
            m = re.match(rf"{pre}(load|down|person)_(\d+(?:\.\d+)?)kg", lab)
            if not m:
                continue
            kind = {"load": "up", "down": "down", "person": "person"}[m.group(1)]
            v = steady(rows, lab)
            if v is not None:
                pts[kind].setdefault(float(m.group(2)), []).append(v)
    summary = {}
    for kind, d in pts.items():
        summary[kind] = {f"{k:g}": {"median_raw": st.median(v), "sd": st.pstdev(v) if len(v) > 1 else 0.0, "n": len(v)}
                         for k, v in sorted(d.items())}
    hyst = []
    for k in pts["up"]:
        if k in pts["down"] and k > 0:
            hyst.append(abs(st.median(pts["down"][k]) - st.median(pts["up"][k])) / 4095 * 100)
    rep = [st.pstdev(v) / st.mean(v) * 100 for v in pts["up"].values() if len(v) > 1 and st.mean(v) > 100]
    summary["hysteresis_pct_fs_max"] = max(hyst) if hyst else None
    summary["repeatability_cv_pct_max"] = max(rep) if rep else None
    all_pts = sorted([(k, st.median(v)) for k, v in pts["up"].items()] + [(k, st.median(v)) for k, v in pts["person"].items()])
    above = [k for k, v in all_pts if v >= 1200]
    summary["first_load_kg_reaching_1200"] = min(above) if above else None
    fig, ax = plt.subplots(figsize=(4.6, 3.2), dpi=200)
    for kind, col, mk, lab in (("up", BLUE, "o", "Weights, loading"), ("down", ORANGE, "s", "Weights, unloading"),
                               ("person", GREEN, "^", "Seated people")):
        xs = sorted(pts[kind])
        if xs:
            ax.errorbar(xs, [st.median(pts[kind][x]) for x in xs],
                        yerr=[st.pstdev(pts[kind][x]) if len(pts[kind][x]) > 1 else 0 for x in xs],
                        color=col, marker=mk, ms=4, lw=1, capsize=2, label=lab)
    ax.axhline(1200, color=GREY, ls=":", lw=0.8)
    ax.set_xlabel("Load on the cushion (kg)")
    ax.set_ylabel("ADC counts (12-bit)")
    ax.legend(fontsize=7, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    stamp(ax, simulated)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "bench_calibration.png"))
    plt.close(fig)
    return summary


def creep(rows, out, simulated):
    lab = next((r["label"] for r in rows if (r["label"] or "").startswith("creep")), None)
    if lab is None:
        return None
    seg = [r for r in rows if r["label"] == lab]
    t0 = seg[0]["ms"]
    ts = [(r["ms"] - t0) / 1000 for r in seg]
    raw = [r["raw"] for r in seg]
    def at(sec):
        vals = [v for t, v in zip(ts, raw) if sec - 2 <= t <= sec + 2]
        return st.median(vals) if vals else None
    a, b = at(10), at(min(600, ts[-1] - 3))
    fig, ax = plt.subplots(figsize=(4.6, 2.8), dpi=200)
    ax.plot([max(t, 0.1) for t in ts], raw, color=BLUE, lw=0.6)
    ax.set_xscale("log")
    ax.set_xlabel("Time under constant load (s)")
    ax.set_ylabel("ADC counts")
    ax.spines[["top", "right"]].set_visible(False)
    stamp(ax, simulated)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "bench_creep.png"))
    plt.close(fig)
    return {"label": lab, "raw_at_10s": a, "raw_at_end": b, "drift_pct": (b - a) / a * 100 if a and b else None,
            "duration_s": ts[-1]}


def posture(rows):
    out = {}
    for lab in dict.fromkeys(r["label"] for r in rows):
        if lab and lab.startswith("pos_"):
            v = steady(rows, lab)
            seg = [r for r in rows if r["label"] == lab]
            out[lab] = {"median_raw": v, "detected_share": sum(1 for r in seg if r["state"] == 1) / len(seg)}
    return out


def noise(rows):
    raw = [r["raw"] for r in rows]
    ema = [r["ema"] for r in rows]
    return {"raw_mean": st.mean(raw), "raw_sd": st.pstdev(raw), "ema_sd": st.pstdev(ema), "max_raw": max(raw),
            "transitions": int(rows[-1]["transitions"])}


def thermal(rows, out, name, simulated, seat_key="t_a", cabin_key="t_b"):
    clf = DifferentialSeatClassifier(ThermalConfig())
    t0 = rows[0]["ms"]
    series, last_s = [], -1
    for r in rows:
        s = int((r["ms"] - t0) / 1000)
        if s == last_s:
            continue
        last_s = s
        state, flag = clf.update(s, r["state"] == 1, r[seat_key], r[cabin_key])
        series.append((s, r["label"], r[seat_key], r[cabin_key], state, flag))
    per = {}
    for lab in dict.fromkeys(x[1] for x in series):
        seg = [x for x in series if x[1] == lab]
        tail = seg[int(len(seg) * 0.5):]
        states = [x[4] for x in tail]
        per[lab] = {"seconds": len(seg), "seat_c_end": tail[-1][2], "cabin_c_end": tail[-1][3],
                    "delta_end": (tail[-1][2] - tail[-1][3]) if tail[-1][2] is not None and tail[-1][3] is not None else None,
                    "state_majority_last_half": max(set(states), key=states.count),
                    "flags": sorted({x[5] for x in tail if x[5]})}
    fig, ax = plt.subplots(2, 1, figsize=(6.4, 3.8), dpi=200, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    xs = [x[0] / 60 for x in series]
    ax[0].plot(xs, [x[2] for x in series], color=BLUE, lw=1.2, label="Seat probe")
    ax[0].plot(xs, [x[3] for x in series], color=ORANGE, lw=1.2, label="Cabin probe")
    ax[0].set_ylabel("°C")
    ax[0].legend(fontsize=7, frameon=False)
    code = {"EMPTY": 0, "OBJECT": 1, "OCCUPIED": 2}
    ax[1].step(xs, [code[x[4]] for x in series], color="black", lw=1, where="post")
    ax[1].set_yticks([0, 1, 2])
    ax[1].set_yticklabels(["EMPTY", "OBJECT", "OCCUPIED"], fontsize=7)
    ax[1].set_xlabel("Time (min)")
    bounds = [x for i, x in enumerate(series) if i == 0 or x[1] != series[i - 1][1]]
    for b in bounds:
        for a in ax:
            a.axvline(b[0] / 60, color=GREY, lw=0.4, ls=":")
        ax[0].text(b[0] / 60, ax[0].get_ylim()[1], b[1], fontsize=6, rotation=90, va="top")
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    stamp(ax[0], simulated)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f"bench_{name}.png"))
    plt.close(fig)
    return per


def ride(rows, out, simulated):
    raw_det = RawThreshold(1200)
    for r in rows:
        raw_det.update(r["raw"])
    old_state, cand, count, old_flips = False, False, 0, 0
    for r in rows[::10]:
        x = r["raw"] >= 1200
        if x == old_state:
            cand, count = x, 0
            continue
        count = count + 1 if x == cand else 1
        cand = x
        if count >= 3:
            old_state, count = x, 0
            old_flips += 1
    per = {}
    for lab in dict.fromkeys(r["label"] for r in rows):
        seg = [r for r in rows if r["label"] == lab]
        az = [r["az"] for r in seg if r["az"] is not None]
        per[lab] = {"rows": len(seg), "loaded_share": sum(1 for r in seg if r["state"] == 1) / len(seg),
                    "az_rms_g": math.sqrt(st.mean([(a - 1.0) ** 2 for a in az])) if az else None}
    return {"filtered_transitions": int(rows[-1]["transitions"]), "raw_10hz_transitions": raw_det.transitions,
            "old_1hz_debounce_transitions": old_flips, "per_label": per}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("out")
    ap.add_argument("--simulated", action="store_true")
    ap.add_argument("--swap-probes", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    files = find(a.folder)
    sk, ck = ("t_b", "t_a") if a.swap_probes else ("t_a", "t_b")
    res = {"simulated": a.simulated, "files": {k: os.path.basename(v) for k, v in files.items()}}
    if "test0_noise" in files:
        res["noise"] = noise(load(files["test0_noise"]))
    if "test1_calibration" in files:
        res["calibration"] = calibration(load(files["test1_calibration"]), a.out, a.simulated)
    if "test2_creep" in files:
        res["creep"] = creep(load(files["test2_creep"]), a.out, a.simulated)
    if "test3_posture" in files:
        res["posture"] = posture(load(files["test3_posture"]))
    for t in ("test4_thermal_room", "test5_thermal_hotcar"):
        if t in files:
            res[t] = thermal(load(files[t]), a.out, t, a.simulated, sk, ck)
    if "test6_ride" in files:
        res["ride"] = ride(load(files["test6_ride"]), a.out, a.simulated)
    json.dump(res, open(os.path.join(a.out, "bench_summary.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
