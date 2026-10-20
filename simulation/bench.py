import json
import math
import os
import platform
import sys
import timeit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reference"))

from transit_core import (
    SeatConfig, classify_seat, SeatDebouncer, OCCUPIED, EMPTY, parse_nmea_rmc, build_nmea_rmc,
    haversine_m, is_stationary, boarding_allowed, slab_policy, stage_policy, per_km_policy, base_fare,
    fare_record, build_seat_summary, encode, build_stop_board, EtaEstimator, verify_rider, IdentityMode, assess_event,
)

N = 50000
cfg = SeatConfig().validate()
deb = SeatDebouncer(cfg)
nmea = build_nmea_rmc(28.6139, 77.2090, 7.5)
fa = {"lat": 28.6139, "lon": 77.2090, "speed_mps": 0.2}
fb = {"lat": 28.61391, "lon": 77.20901, "speed_mps": 0.1}
slab = slab_policy([(4, 5), (10, 10), (math.inf, 15)])
stage = stage_policy(2.0, [6, 8, 10, 12, 14])
perkm = per_km_policy(1.0, 5.0)
states = [EMPTY] * 30 + [OCCUPIED] * 14
arrivals = [{"route": "21", "bus": f"B{i}", "eta_s": 100 * i, "free_seats": i, "updated_s": 0} for i in range(6)]
eta = EtaEstimator()
states_cycle = [OCCUPIED, OCCUPIED, EMPTY]

cases = {
    "Seat classification (pressure + temperature band)": lambda: classify_seat(2600, 35.1, cfg),
    "Debounce update (one seat)": lambda: deb.update(OCCUPIED),
    "NMEA RMC parse + checksum": lambda: parse_nmea_rmc(nmea),
    "Haversine distance": lambda: haversine_m(28.6139, 77.2090, 28.6200, 77.2150),
    "Stationary check (two fixes)": lambda: is_stationary(fa, fb),
    "Boarding-gate AND check": lambda: boarding_allowed(True, True),
    "Rider verification (public ticket)": lambda: verify_rider(IdentityMode.PUBLIC_TICKET, "NCMC:12345678", None),
    "Fare: distance slab": lambda: base_fare(slab, 6.2),
    "Fare: stage table": lambda: base_fare(stage, 6.2),
    "Fare: per-km": lambda: base_fare(perkm, 6.2),
    "Universal fare record": lambda: fare_record("T1", "abc", "NCMC", "S01", "S09", 6.2, slab),
    "Seat summary build + JSON encode (44 seats)": lambda: encode(build_seat_summary("B1", "21", 1, fa, states, False, 0)),
    "Stop board build (6 candidates, 4 rows)": lambda: build_stop_board("S05", "Stop 5", arrivals, 50),
    "ETA estimate": lambda: eta.eta_s(1800, 3),
    "Escalation assessment (T1-T3)": lambda: assess_event({"occupied_seats": 30, "validated_tickets": 28}),
}

def full_cycle():
    f1 = parse_nmea_rmc(nmea)
    is_stationary(fa, f1)
    classify_seat(2600, 35.1, cfg)
    boarding_allowed(True, True)
    d = haversine_m(28.6139, 77.2090, 28.6200, 77.2150) / 1000.0
    base_fare(slab, d)
    assess_event({"occupied_seats": 30, "validated_tickets": 28})

cases["FULL per-event cycle"] = full_cycle

out = {"python": platform.python_version(), "machine": platform.machine(), "processor": platform.processor(), "iterations": N, "us_per_call": {}}
for name, fn in cases.items():
    best = min(timeit.repeat(fn, number=N, repeat=5))
    out["us_per_call"][name] = best / N * 1e6
    print(f"{name:50s} {out['us_per_call'][name]:.3f} us")
json.dump(out, open(os.path.join(HERE, "results", "bench.json"), "w"), indent=1)
