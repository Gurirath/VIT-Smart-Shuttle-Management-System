"""Signal-level study of the seat pressure channel under road vibration (Section 4, physical sensor characterization).

The FSR model, vibration and shock levels are modelling assumptions until bench and ride logs replace them.
"""
import json
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reference"))
from transit_core import FilterConfig, SeatSignalFilter

FIG = os.path.join(HERE, "..", "figures")
RES = os.path.join(HERE, "results")

FS = 10.0
VREF = 3.3
R_FIX = 10_000.0
FSR_A = 12_300.0
FSR_B = 1.30
G = 9.81
FSR_AREA_M2 = 1.27e-4
CONTACT_AREA_M2 = 0.09
PEAK_FACTOR = 2.2
FOAM_TRANSMISSION = 0.85
VIB_RMS = 0.7
SHOCKS_PER_MIN = 2.0
SHOCK_G = (0.4, 1.4)
SHOCK_LEN_S = (0.08, 0.25)
CREEP_PER_DECADE = 0.05
ADC_NOISE = 25.0
SEED = 11

BLUE, ORANGE, GREEN, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#666666"


def fsr_resistance(force_n):
    f = np.maximum(force_n, 0.05)
    return FSR_A * f ** (-FSR_B)


def adc_counts(force_n):
    r = fsr_resistance(force_n)
    v = VREF * R_FIX / (R_FIX + r)
    return np.clip(v / VREF * 4095.0, 0, 4095)


def force_on_fsr(mass_kg, posture=1.0):
    pressure = mass_kg * G / CONTACT_AREA_M2 * PEAK_FACTOR * posture
    return pressure * FSR_AREA_M2 * FOAM_TRANSMISSION


def calibration_curve():
    masses = np.arange(0, 101, 1)
    centred = adc_counts(force_on_fsr(masses, 1.0))
    offset = adc_counts(force_on_fsr(masses, 0.45))
    return masses, centred, offset


def scenario(rng, duration_s=3600):
    n = int(duration_s * FS)
    t = np.arange(n) / FS
    segments = [(0, 900, 0.0, "empty", 1.0), (900, 2100, 70.0, "person 70 kg", 1.0),
                (2100, 2700, 55.0, "person 55 kg, off-centre", 0.6), (2700, 3300, 8.0, "bag 8 kg", 1.0),
                (3300, 3600, 0.0, "empty", 1.0)]
    mass = np.zeros(n)
    posture = np.ones(n)
    truth = np.zeros(n, dtype=bool)
    load_start = np.zeros(n)
    for a, b, m, label, pf in segments:
        i0, i1 = int(a * FS), int(b * FS)
        mass[i0:i1] = m
        posture[i0:i1] = pf
        truth[i0:i1] = m >= 30.0
        load_start[i0:i1] = a
    freqs = rng.uniform(1.0, 20.0, 24)
    phases = rng.uniform(0, 2 * math.pi, 24)
    amps = rng.uniform(0.5, 1.0, 24)
    vib = sum(a * np.sin(2 * math.pi * f * t + p) for a, f, p in zip(amps, freqs, phases))
    vib = vib / np.sqrt(np.mean(vib ** 2)) * VIB_RMS
    shocks = np.zeros(n)
    k = rng.poisson(SHOCKS_PER_MIN * duration_s / 60.0)
    for start in rng.uniform(0, duration_s, k):
        length = rng.uniform(*SHOCK_LEN_S)
        peak = rng.uniform(*SHOCK_G) * G * rng.choice([-1.0, 1.0])
        i0 = int(start * FS)
        i1 = min(n, i0 + max(1, int(length * FS)))
        m = i1 - i0
        shocks[i0:i1] += peak * np.sin(math.pi * (np.arange(m) + 0.5) / m)
    accel = vib + shocks
    elapsed = np.maximum(t - load_start, 1.0)
    creep = 1.0 + CREEP_PER_DECADE * np.log10(elapsed)
    force = force_on_fsr(mass, posture) * np.clip(1.0 + accel / G, 0.0, 3.0) * np.where(mass > 0, creep, 1.0)
    empty_force = 0.03 * np.clip(1.0 + accel / G, 0.0, 3.0)
    force = np.where(mass > 0, force, empty_force)
    raw = adc_counts(force) + rng.normal(0, ADC_NOISE, n)
    raw += np.where(mass == 0, 120.0 + 60.0 * t / duration_s, 0.0)
    return t, np.clip(raw, 0, 4095), truth, mass, segments, accel


def old_design(raw, truth):
    step = int(FS)
    samples = raw[::step]
    state, cand, count, flips = False, False, 0, 0
    out = np.zeros_like(truth)
    for i, v in enumerate(samples):
        r = v >= 1200
        if r == state:
            cand, count = r, 0
        else:
            if r == cand:
                count += 1
            else:
                cand, count = r, 1
            if count >= 3:
                state = r
                count = 0
                flips += 1
        out[i * step:(i + 1) * step] = state
    return out, flips


def raw_10hz(raw):
    st = raw >= 1200
    return st, int(np.sum(st[1:] != st[:-1]))


def new_design(raw, cfg=None):
    f = SeatSignalFilter(cfg or FilterConfig())
    out = np.zeros(len(raw), dtype=bool)
    ema = np.zeros(len(raw))
    for i, v in enumerate(raw):
        out[i] = f.update(v)
        ema[i] = f.ema - f.baseline
    return out, f.transitions, ema


def latency(states, truth):
    lat = []
    edges = np.where(truth[1:] != truth[:-1])[0] + 1
    for e in edges:
        target = truth[e]
        j = e
        while j < len(states) and states[j] != target:
            j += 1
        lat.append((j - e) / FS)
    return lat


def ema_gain(f_hz, alpha, fs=FS):
    w = 2 * math.pi * f_hz / fs
    return alpha / abs(1 - (1 - alpha) * complex(math.cos(w), -math.sin(w)))


def main():
    rng = np.random.default_rng(SEED)
    t, raw, truth, mass, segments, accel = scenario(rng)
    s_old, flips_old = old_design(raw, truth)
    s_raw, flips_raw = raw_10hz(raw)
    s_new, flips_new, ema = new_design(raw)
    true_edges = int(np.sum(truth[1:] != truth[:-1]))

    def summary(states, flips):
        lat = latency(states, truth)
        return {"transitions": int(flips), "false_transitions": int(max(0, flips - true_edges)),
                "error_share": float(np.mean(states != truth)), "latency_s": [round(x, 2) for x in lat]}

    runs = []
    for s in range(20):
        r2 = np.random.default_rng(100 + s)
        _, rw, tr, *_ = scenario(r2)
        te = int(np.sum(tr[1:] != tr[:-1]))
        runs.append({"old": max(0, old_design(rw, tr)[1] - te), "raw": max(0, raw_10hz(rw)[1] - te),
                     "new": max(0, new_design(rw)[1] - te)})
    masses, cal_c, cal_o = calibration_curve()
    threshold_mass = float(masses[np.argmax(cal_c >= 1200)])
    threshold_mass_offset = float(masses[np.argmax(cal_o >= 1200)]) if (cal_o >= 1200).any() else None
    cfg = FilterConfig()
    out = {
        "assumptions": {"fs_hz": FS, "vib_rms_ms2": VIB_RMS, "shocks_per_min": SHOCKS_PER_MIN, "shock_g": SHOCK_G,
                        "fsr_model": f"R = {FSR_A:.0f} * F^-{FSR_B}", "divider_ohm": R_FIX, "contact_area_m2": CONTACT_AREA_M2,
                        "peak_factor": PEAK_FACTOR, "creep_per_decade": CREEP_PER_DECADE},
        "true_edges": true_edges,
        "seed_run": {"old_1hz_debounce": summary(s_old, flips_old), "raw_10hz": summary(s_raw, flips_raw),
                     "median_ema_hysteresis": summary(s_new, flips_new)},
        "false_transitions_per_hour_20_runs": {k: {"mean": float(np.mean([r[k] for r in runs])), "max": int(max(r[k] for r in runs))}
                                               for k in ("old", "raw", "new")},
        "ema_time_constant_s": cfg.ema_time_constant_s(),
        "ema_cutoff_hz": -math.log(1 - cfg.ema_alpha) * FS / (2 * math.pi),
        "ema_gain": {f"{f}": ema_gain(f, cfg.ema_alpha) for f in (0.1, 0.5, 1.0, 2.0, 5.0)},
        "calibration_model": {"threshold_mass_centred_kg": threshold_mass, "threshold_mass_off_centre_kg": threshold_mass_offset,
                              "adc_at_kg": {str(m): float(cal_c[m]) for m in (10, 30, 45, 70, 100)}},
    }
    os.makedirs(RES, exist_ok=True)
    json.dump(out, open(os.path.join(RES, "sensor_filter.json"), "w"), indent=1)

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.8), dpi=200, sharex=True)
    a, b = int(880 * FS), int(1000 * FS)
    tt = t[a:b]
    axes[0].plot(tt, raw[a:b], color=GREY, lw=0.6, label="Raw ADC (10 Hz)")
    axes[0].plot(tt, ema[a:b], color=BLUE, lw=1.4, label="Median + EMA, baseline removed")
    axes[0].axhline(1200, color=ORANGE, ls="--", lw=0.9, label="Enter 1,200")
    axes[0].axhline(1000, color=GREEN, ls=":", lw=0.9, label="Exit 1,000")
    axes[0].set_ylabel("ADC counts")
    axes[0].legend(loc="upper left", fontsize=7, ncol=2, frameon=False)
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[1].step(tt, truth[a:b].astype(int) + 2.4, color="black", lw=1, where="post")
    axes[1].step(tt, s_old[a:b].astype(int) + 1.2, color=GREY, lw=1, where="post")
    axes[1].step(tt, s_new[a:b].astype(int), color=BLUE, lw=1.2, where="post")
    axes[1].set_yticks([0.5, 1.7, 2.9])
    axes[1].set_yticklabels(["Filtered (10 Hz)", "Old (1 Hz, 3-sample)", "True occupancy"])
    axes[1].set_xlabel("Time in ride (s)")
    axes[1].spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_filter_trace.png"))
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.9), dpi=200)
    ax[0].plot(masses, cal_c, color=BLUE, lw=1.6, label="FSR under the seat bones")
    ax[0].plot(masses, cal_o, color=ORANGE, lw=1.4, ls="--", label="FSR off-centre")
    ax[0].axhline(1200, color=GREY, lw=0.8, ls=":")
    ax[0].set_xlabel("Occupant mass (kg)")
    ax[0].set_ylabel("ADC counts")
    ax[0].legend(fontsize=7, frameon=False, loc="lower right")
    ax[0].spines[["top", "right"]].set_visible(False)
    labels = ["Raw 10 Hz", "Old 1 Hz +\n3-sample", "Median + EMA\n+ hysteresis"]
    vals = [out["false_transitions_per_hour_20_runs"][k]["mean"] for k in ("raw", "old", "new")]
    ax[1].bar(labels, vals, color=[GREY, ORANGE, BLUE])
    for i, v in enumerate(vals):
        ax[1].text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=8)
    ax[1].set_ylabel("False state changes per hour")
    ax[1].set_ylim(0, max(vals) * 1.18 + 1)
    ax[1].spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_sensor_model.png"))
    plt.close(fig)
    print(json.dumps({k: out[k] for k in ("false_transitions_per_hour_20_runs", "calibration_model", "ema_cutoff_hz")}, indent=1))
    print(json.dumps(out["seed_run"], indent=1)[:1500])


if __name__ == "__main__":
    main()
