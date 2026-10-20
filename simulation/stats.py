"""Paired statistics for the main runs and the sensitivity variants (Section 6.3, Table 22).

Pairs scenario B_real with scenario A by seed (common random numbers) and writes
results/stats.json. Uses the raw result_*.json files when they exist (after running
runall.sh and runsens.sh) and falls back to results/run_summaries.json otherwise.
"""
import json
import os
import statistics as st
from glob import glob

from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
SUMMARIES = os.path.join(HERE, "results", "run_summaries.json")


def summarise(r):
    return {
        "seekers": r["seekers"],
        "seekers_seated_at_board": r["seekers_seated_at_board"],
        "seeker_mean_wait_s": st.mean(r["seeker_wait_s"]),
        "all_mean_wait_s": st.mean(r["all_wait_s"]),
        "left_behind_events": r["left_behind_events"],
        "skippers": r["skippers"],
    }


def per_run(s):
    return {
        "seated": s["seekers_seated_at_board"] / s["seekers"],
        "seeker_wait": s["seeker_mean_wait_s"] / 60,
        "all_wait": s["all_mean_wait_s"] / 60,
        "refusals": s["left_behind_events"],
        "skip_share": s["skippers"] / s["seekers"],
    }


def load(variant, scenario):
    d = os.path.join(HERE, "results") if variant == "main" else os.path.join(HERE, "results_sens", variant)
    out = {}
    for f in glob(os.path.join(d, f"result_{scenario}_*.json")):
        seed = int(f.rsplit("_", 1)[1].split(".")[0])
        out[seed] = per_run(summarise(json.load(open(f))))
    if out or not os.path.exists(SUMMARIES):
        return out
    for key, s in json.load(open(SUMMARIES)).get(variant, {}).items():
        sc, seed = key.rsplit("_", 1)
        if sc == scenario:
            out[int(seed)] = per_run(s)
    return out


def paired(variant):
    a, b = load(variant, "A"), load(variant, "B_real")
    seeds = sorted(set(a) & set(b))
    res = {"seeds": seeds}
    for k in ["seated", "seeker_wait", "all_wait", "refusals"]:
        diff = [b[s][k] - a[s][k] for s in seeds]
        m = st.mean(diff)
        e = {"A": st.mean(a[s][k] for s in seeds), "B": st.mean(b[s][k] for s in seeds), "diff": m,
             "positive_seeds": sum(x > 0 for x in diff), "negative_seeds": sum(x < 0 for x in diff)}
        if len(seeds) > 1 and st.stdev(diff) > 0:
            t = stats.ttest_rel([b[s][k] for s in seeds], [a[s][k] for s in seeds])
            e.update(t=float(t.statistic), p=float(t.pvalue), dz=m / st.stdev(diff))
        res[k] = e
    res["refusal_change"] = res["refusals"]["diff"] / res["refusals"]["A"]
    res["skip_share"] = st.mean(b[s]["skip_share"] for s in seeds)
    return res


VARIANTS = ["seek40", "seek80", "tolhalf", "outage3x", "demand120", "demand80"]

if __name__ == "__main__":
    out = {"main": paired("main"), "sens": {v: paired(v) for v in VARIANTS}}
    json.dump(out, open(os.path.join(HERE, "results", "stats.json"), "w"), indent=1)
    m = out["main"]
    print("main", {k: (round(m[k]["diff"], 4), round(m[k].get("p", 1), 5)) for k in ["seated", "seeker_wait", "all_wait", "refusals"]}, round(m["refusal_change"], 3))
    for n, v in out["sens"].items():
        print(n, v["seeds"], round(v["seated"]["diff"], 4), round(v["seeker_wait"]["diff"], 3), round(v["refusal_change"], 3), round(v["skip_share"], 3))
