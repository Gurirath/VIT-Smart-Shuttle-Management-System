import json
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reference"))

from transit_core import build_seat_summary, encode, build_stop_board, EMPTY, OCCUPIED

STOPS_PER_ROUTE = 25
SEG_TIME = 125.0


def make_city(n_buses, n_routes, n_stops, rng):
    routes = []
    for r in range(n_routes):
        routes.append(rng.sample(range(n_stops), STOPS_PER_ROUTE))
    stop_routes = defaultdict(list)
    for r, stops in enumerate(routes):
        for k, s in enumerate(stops):
            stop_routes[s].append((r, k))
    buses = []
    for b in range(n_buses):
        r = b % n_routes
        buses.append({"bus": f"B{b:05d}", "route": r, "served": rng.randrange(-1, STOPS_PER_ROUTE - 1), "frac": rng.random()})
    return routes, stop_routes, buses


def run(n_buses, n_routes=2000, n_stops=5000, cycles=3, seed=7):
    rng = random.Random(seed)
    routes, stop_routes, buses = make_city(n_buses, n_routes, n_stops, rng)
    states = [EMPTY] * 30 + [OCCUPIED] * 14
    msgs = []
    for b in buses:
        fix = {"lat": 28.6 + rng.random() * 0.2, "lon": 77.1 + rng.random() * 0.2, "speed_mps": rng.random() * 10}
        s = build_seat_summary(b["bus"], str(b["route"]), 1, fix, states, False, 1000)
        s["served"] = b["served"]
        s["frac"] = b["frac"]
        msgs.append(encode(s))
    ingest, boards_t, rows_total = [], [], 0
    for c in range(cycles):
        state = {}
        by_route = defaultdict(list)
        t0 = time.perf_counter()
        for m in msgs:
            d = json.loads(m)
            state[d["bus"]] = d
        for d in state.values():
            by_route[int(d["route"])].append(d)
        t1 = time.perf_counter()
        n_rows = 0
        for s, rk in stop_routes.items():
            arrivals = []
            for r, k in rk:
                for d in by_route[r]:
                    if d["served"] >= k:
                        continue
                    eta = SEG_TIME * (k - d["served"] - 1 + d["frac"])
                    arrivals.append({"route": str(r), "bus": d["bus"], "eta_s": eta, "free_seats": d["free_seats"], "updated_s": d["ts"]})
            bd = build_stop_board(f"S{s}", "", arrivals, 1005)
            n_rows += len(bd["rows"])
        t2 = time.perf_counter()
        ingest.append(t1 - t0)
        boards_t.append(t2 - t1)
        rows_total = n_rows
    return {"buses": n_buses, "routes": n_routes, "stops": n_stops, "ingest_s": min(ingest), "boards_s": min(boards_t),
            "cycle_s": min(ingest) + min(boards_t), "rows": rows_total, "msg_bytes_mean": sum(len(m) for m in msgs) / len(msgs)}


if __name__ == "__main__":
    out = []
    for n in (500, 1000, 2500, 5000, 7582):
        r = run(n)
        out.append(r)
        print(r)
    json.dump(out, open(os.path.join(HERE, "results", "loadtest.json"), "w"), indent=1)
