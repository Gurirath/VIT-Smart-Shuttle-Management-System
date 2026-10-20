import heapq
import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reference"))

import libsumo as traci
import sumo

from build_scenario import build, SIM_END, STOP_POS, STOP_LEN
from transit_core import (
    SeatConfig, configure_for_environment, EMPTY, OBJECT, OCCUPIED, build_seat_summary, encode,
    build_sms_summary, build_nmea_rmc, parse_nmea_rmc, build_stop_board, IdentityMode, verify_rider,
    fare_record, slab_policy, stage_policy, per_km_policy, flat_policy,
)

SEATS = 44
STANDING = 25
LAT0, LON0 = 28.6139, 77.2090
M_PER_DEG_LAT = 111320.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(LAT0))

DEMAND_SCALE = float(os.environ.get("DEMAND_SCALE", "1.0"))
ARRIVAL_PER_MIN = [v * DEMAND_SCALE for v in [1.5] * 12 + [0.8] * 5 + [0.4] * 2 + [0.0]]
SEEK_PROB = float(os.environ.get("SEEK_PROB", "0.6"))
WTW_RANGE_S = tuple(float(x) for x in os.environ.get("WTW_RANGE_S", "120,780").split(","))
DWELL_BASE, DWELL_BOARD, DWELL_ALIGHT = 10.0, 2.0, 1.5
PUBLISH_EVERY = 10
SMS_EVERY = 30
BOARD_EVERY = 10
DISPLAY_LAG = 1
WEAK_EDGES = {6}
DEAD_EDGES = {13}
OUTAGE_RATE = 1 / float(os.environ.get("OUTAGE_EVERY_S", "1800"))
OUTAGE_MEAN_S = 60
MAIN_AMBIENT = 31.0
AMBIENTS = [22.0, 25.0, 28.0, 30.0, 31.0, 32.0, 34.0, 36.0, 38.0, 40.0]
BAG_PROB = 0.08
LIGHT_BAG_PROB = 0.3
TAU_S = 45.0
FARE_POLICIES = {
    "three-slab": slab_policy([(4, 5), (10, 10), (math.inf, 15)], name="three-slab"),
    "stage-2km": stage_policy(2.0, [6, 8, 10, 12, 14, 16, 18], name="stage-2km"),
    "per-km": per_km_policy(1.0, 5.0, name="per-km"),
    "flat": flat_policy(10.0, name="flat"),
}


def to_latlon(x, y):
    return LAT0 + (y - 400.0) / M_PER_DEG_LAT, LON0 + x / M_PER_DEG_LON


class Passenger:
    __slots__ = ("pid", "origin", "dest", "t_arrive", "wants_seat", "wtw", "t_board", "seated_at_board",
                 "seat_time", "stand_time", "skips", "t_first_skip", "bus", "credential", "female_free")

    def __init__(self, pid, origin, dest, t, rng):
        self.pid = pid
        self.origin = origin
        self.dest = dest
        self.t_arrive = t
        self.wants_seat = rng.random() < SEEK_PROB
        self.wtw = rng.uniform(*WTW_RANGE_S)
        self.t_board = None
        self.seated_at_board = False
        self.seat_time = 0.0
        self.stand_time = 0.0
        self.skips = 0
        self.t_first_skip = None
        self.bus = None
        media = ("NCMC", "QR", "ETM", "PASS")
        self.credential = f"{media[rng.integers(0, 4)]}:{pid:08d}"
        self.female_free = rng.random() < 0.3


class Bus:
    def __init__(self, vid, rng):
        self.vid = vid
        self.seat_occ = [None] * SEATS
        self.seat_obj = [None] * SEATS
        self.obj_light = [False] * SEATS
        self.sit_time = np.zeros(SEATS)
        self.skin = np.full(SEATS, 35.3)
        self.standing = []
        self.onboard = {}
        self.served = -1
        self.dwell_until = None
        self.door_open = False
        self.debounce_state = [EMPTY] * SEATS
        self.debounce_cand = [EMPTY] * SEATS
        self.debounce_count = [0] * SEATS
        self.est_states = [EMPTY] * SEATS
        self.seq = 0
        self.last_pub = -999
        self.last_sms = -999
        self.outage_until = -1
        self.prev_fix = None
        self.msgs = {"primary": 0, "sms": 0, "bytes_primary": 0, "bytes_sms": 0, "buffered": 0}
        self.rng = rng
        self.age = 0

    def load(self):
        return len(self.onboard)

    def gt_free(self):
        return sum(1 for i in range(SEATS) if self.seat_occ[i] is None and self.seat_obj[i] is None)

    def free_seat_indices(self):
        return [i for i in range(SEATS) if self.seat_occ[i] is None and self.seat_obj[i] is None]


class Cloud:
    def __init__(self, name, stop_x):
        self.name = name
        self.state = {}
        self.stop_x = stop_x
        self.boards = {}
        default = 600.0 / 6.0 + 25.0
        self.seg_time = [default] * len(stop_x)
        self.last_stop = {}

    def receive(self, rep):
        b = rep["bus"]
        prev = self.state.get(b)
        if prev and rep["ts"] <= prev["ts"]:
            return
        s = rep["served"]
        ls = self.last_stop.get(b)
        if ls is None or s > ls[0]:
            if ls is not None and s == ls[0] + 1 and s >= 1:
                seg = rep["ts"] - ls[1]
                if 20 < seg < 1800:
                    self.seg_time[s] = 0.5 * seg + 0.5 * self.seg_time[s]
            self.last_stop[b] = (s, rep["ts"])
        self.state[b] = rep

    def drop(self, b):
        self.state.pop(b, None)
        self.last_stop.pop(b, None)

    def eta(self, r, si, now):
        s = r["served"]
        nxt = s + 1
        if nxt > si:
            return None
        prev_x = self.stop_x[s] if s >= 0 else self.stop_x[0] - 600.0
        span = max(1.0, self.stop_x[nxt] - prev_x)
        frac = min(1.0, max(0.0, (self.stop_x[nxt] - r["x"]) / span))
        rem = self.seg_time[nxt] * frac - (now - r["ts"])
        rem = max(0.0, rem)
        for k in range(nxt + 1, si + 1):
            rem += self.seg_time[k]
        return rem

    def make_boards(self, now):
        out = {}
        for si, sx in enumerate(self.stop_x):
            arrivals = []
            for b, r in self.state.items():
                if r["served"] >= si:
                    continue
                e = self.eta(r, si, now)
                if e is None:
                    continue
                arrivals.append({"route": "21", "bus": b, "eta_s": e, "free_seats": r["free"], "updated_s": r["ts"]})
            out[si] = build_stop_board(f"S{si+1:02d}", f"Stop {si+1}", arrivals, now)
        self.boards = out
        return out


def link_mode(bus, edge_idx, t):
    if edge_idx in DEAD_EDGES:
        return "none"
    if edge_idx in WEAK_EDGES or t < bus.outage_until:
        return "sms"
    return "primary"


def run(seed, scenario, out_dir, ambient=MAIN_AMBIENT):
    rng = np.random.default_rng(seed * 1000 + {"A": 1, "B_real": 2, "B_oracle": 3}[scenario])
    demand_rng = np.random.default_rng(seed)
    sc = build(seed)
    edges = sc["edges"]
    stop_x = [x0 + STOP_POS + STOP_LEN / 2 for x0 in sc["edge_x0"]]
    nstops = len(stop_x)
    cfg = configure_for_environment(SeatConfig().validate(), ambient)
    default_cfg = SeatConfig().validate()
    cmd = [os.path.join(sumo.SUMO_HOME, "bin", "sumo"), "-n", sc["net"], "-a", sc["stops"],
           "-r", ",".join(sc["routes"]), "--step-length", "1", "--no-step-log", "true",
           "--no-warnings", "true", "--seed", str(seed), "--time-to-teleport", "300",
           "--end", str(SIM_END)]
    traci.start(cmd)

    clouds = {"fallback": Cloud("fallback", stop_x), "primary_only": Cloud("primary_only", stop_x), "oracle": Cloud("oracle", stop_x)}
    shown = {k: {} for k in clouds}
    display_queue = {k: None for k in clouds}
    msg_stats = []
    tiebreak = 0
    pending = []
    waiting = [[] for _ in range(nstops)]
    passengers = []
    buses = {}
    pid = 0
    arrivals_log = []
    eta_preds = defaultdict(list)
    staleness = {k: [] for k in clouds}
    free_err_t = []
    conf = {a: {"fixed": np.zeros((2, 2), dtype=np.int64), "env": np.zeros((2, 2), dtype=np.int64)} for a in AMBIENTS}
    trips = []
    fares = []
    traj = []
    snapshots = {}
    left_behind = 0
    t0 = time.time()
    t = 0
    finished = set()

    while t < SIM_END:
        traci.simulationStep()
        t = int(traci.simulation.getTime())

        for si in range(nstops):
            lam = ARRIVAL_PER_MIN[si] / 60.0
            if 300 <= t <= SIM_END - 1200 and lam > 0:
                for _ in range(demand_rng.poisson(lam)):
                    k = 1 + demand_rng.poisson(5)
                    dest = min(nstops - 1, si + k)
                    if dest <= si:
                        continue
                    p = Passenger(pid, si, dest, t, demand_rng)
                    pid += 1
                    passengers.append(p)
                    waiting[si].append(p)

        while pending and pending[0][0] <= t:
            _, _, cname, rep = heapq.heappop(pending)
            clouds[cname].receive(rep)

        active = set(traci.vehicle.getIDList())
        for vid in list(buses):
            if vid not in active:
                for c in clouds.values():
                    c.drop(vid)
                finished.add(vid)
                msg_stats.append(dict(buses[vid].msgs, bus=vid, seconds=buses[vid].age))
                del buses[vid]
        for vid in active:
            if vid.startswith("bus") and vid not in buses and vid not in finished:
                buses[vid] = Bus(vid, np.random.default_rng(rng.integers(1 << 30)))

        for vid, bus in buses.items():
            x, y = traci.vehicle.getPosition(vid)
            v = traci.vehicle.getSpeed(vid)
            road = traci.vehicle.getRoadID(vid)
            edge_idx = edges.index(road) if road in edges else min(nstops - 1, int(x // 600))
            lat, lon = to_latlon(x, y)
            fix = parse_nmea_rmc(build_nmea_rmc(lat, lon, v))
            bus.x, bus.v = x, v
            bus.age += 1
            if t % 10 == 0:
                traj.append((vid, t, round(x, 1), bus.load(), bus.gt_free()))

            if bus.dwell_until is None and traci.vehicle.isStopped(vid):
                stops = traci.vehicle.getStops(vid, 1)
                if stops and stops[0].arrival >= 0 and stops[0].stoppingPlaceID.startswith("S"):
                    si = int(stops[0].stoppingPlaceID[1:]) - 1
                    if si > bus.served:
                        arrivals_log.append(arrival_record(bus, si, t, clouds, shown))
                        nb, na, lb = serve_stop(bus, si, t, waiting, scenario, shown, rng, trips, fares)
                        left_behind += lb
                        bus.dwell_until = t + DWELL_BASE + DWELL_BOARD * nb + DWELL_ALIGHT * na
                        bus.door_open = True
                        bus.served = si
            elif bus.dwell_until is not None and t >= bus.dwell_until:
                bus.dwell_until = None
                bus.door_open = False
                bus.last_pub = -999
                try:
                    traci.vehicle.resume(vid)
                except Exception:
                    pass

            for p in bus.onboard.values():
                if p.pid in bus.seat_occ:
                    p.seat_time += 1
                else:
                    p.stand_time += 1

            if bus.outage_until < t and rng.random() < OUTAGE_RATE:
                bus.outage_until = t + rng.exponential(OUTAGE_MEAN_S)

            sense(bus, t, cfg, default_cfg, conf, ambient)
            est_free = sum(1 for s in bus.est_states if s == EMPTY)
            gt = bus.gt_free()
            free_err_t.append(est_free - gt)

            orep = {"bus": vid, "x": x, "v": v, "free": gt, "ts": t, "served": bus.served}
            clouds["oracle"].receive(orep)

            mode = link_mode(bus, edge_idx, t)
            due_primary = (t - bus.last_pub) >= PUBLISH_EVERY
            if due_primary:
                bus.seq += 1
                summ = build_seat_summary(vid, "21", bus.seq, fix, bus.est_states, bus.door_open, t)
                rep = {"bus": vid, "x": x, "v": v, "free": summ["free_seats"], "ts": t, "served": bus.served}
                bus.last_pub = t
                if mode == "primary":
                    lat_s = float(np.clip(rng.lognormal(math.log(0.3), 0.5), 0.05, 5.0))
                    bus.msgs["primary"] += 1
                    bus.msgs["bytes_primary"] += len(encode(summ).encode())
                    for cname in ("fallback", "primary_only"):
                        tiebreak += 1
                        heapq.heappush(pending, (t + math.ceil(lat_s), tiebreak, cname, rep))
                else:
                    bus.msgs["buffered"] += 1
                    if mode == "sms" and (t - bus.last_sms) >= SMS_EVERY:
                        bus.last_sms = t
                        bus.msgs["sms"] += 1
                        bus.msgs["bytes_sms"] += len(build_sms_summary(summ))
                        lat_s = float(np.clip(rng.normal(5, 2), 1, 20))
                        tiebreak += 1
                        heapq.heappush(pending, (t + math.ceil(lat_s), tiebreak, "fallback", rep))

        if t % BOARD_EVERY == 0:
            for cname, c in clouds.items():
                boards = c.make_boards(t)
                for si, bd in boards.items():
                    for row in bd["rows"]:
                        eta_preds[cname].append((row["bus"], si, t, row["eta_min"] * 60, row["data_age_s"]))
                        staleness[cname].append(row["data_age_s"])
                display_queue[cname] = (t + DISPLAY_LAG, boards)
                if cname == "fallback" and t in (3600, 5400, 7200):
                    snapshots[str(t)] = boards
        for cname in clouds:
            pend = display_queue[cname]
            if pend and t >= pend[0]:
                shown[cname] = {"boards": pend[1]}
                display_queue[cname] = None

    traci.close()
    wall = time.time() - t0

    for vid, b in buses.items():
        msg_stats.append(dict(b.msgs, bus=vid, seconds=b.age))
    result = summarise(seed, scenario, passengers, arrivals_log, eta_preds, staleness, free_err_t, conf,
                       buses_msgs=msg_stats, left_behind=left_behind, trips=trips, fares=fares, wall=wall)
    result["traj"] = traj
    result["snapshots"] = snapshots
    with open(os.path.join(out_dir, f"result_{scenario}_{seed}.json"), "w") as f:
        json.dump(result, f)
    return result


def display_for(shown, cname, si):
    s = shown.get(cname, {})
    boards = s.get("boards")
    if not boards:
        return None
    return boards.get(si)


def arrival_record(bus, si, t, clouds, shown):
    rec = {"bus": bus.vid, "stop": si, "t": t, "gt_free": bus.gt_free(), "load": bus.load()}
    for cname in clouds:
        bd = display_for(shown, cname, si)
        val = None
        if bd:
            for row in bd["rows"]:
                if row["bus"] == bus.vid:
                    val = row["free_seats"]
                    break
        rec[f"shown_{cname}"] = val
    return rec


def skip_decision(p, bus, si, t, scenario, shown):
    if scenario == "A" or not p.wants_seat:
        return False
    cname = "fallback" if scenario == "B_real" else "oracle"
    bd = display_for(shown, cname, si)
    if not bd:
        return False
    this_row = None
    later = []
    for row in bd["rows"]:
        if row["bus"] == bus.vid:
            this_row = row
        else:
            later.append(row)
    if this_row is None or this_row["free_seats"] > 0:
        return False
    tolerance = p.wtw - (t - p.t_first_skip if p.t_first_skip is not None else 0)
    for row in later:
        if row["bus"] != bus.vid and row["free_seats"] > 0 and row["eta_min"] * 60 <= tolerance and row["eta_min"] * 60 > 0:
            return True
    return False


def take_seat(bus, p):
    free = bus.free_seat_indices()
    if not free:
        for i in range(SEATS):
            if bus.seat_occ[i] is None and bus.seat_obj[i] is not None:
                bus.seat_obj[i] = None
                bus.obj_light[i] = False
                free = [i]
                break
    if not free:
        return False
    i = free[0]
    bus.seat_occ[i] = p.pid
    bus.sit_time[i] = 0.0
    bus.skin[i] = bus.rng.normal(35.3, 0.7)
    seated = sum(1 for s in bus.seat_occ if s is not None)
    if seated < 0.6 * SEATS and bus.rng.random() < BAG_PROB:
        rest = bus.free_seat_indices()
        if rest:
            j = rest[0]
            bus.seat_obj[j] = p.pid
            bus.obj_light[j] = bus.rng.random() < LIGHT_BAG_PROB
    return True


def serve_stop(bus, si, t, waiting, scenario, shown, rng, trips, fares):
    alight = [p for p in bus.onboard.values() if p.dest == si]
    for p in alight:
        del bus.onboard[p.pid]
        for i in range(SEATS):
            if bus.seat_occ[i] == p.pid:
                bus.seat_occ[i] = None
            if bus.seat_obj[i] == p.pid:
                bus.seat_obj[i] = None
                bus.obj_light[i] = False
        if p in bus.standing:
            bus.standing.remove(p)
        dist_km = (p.dest - p.origin) * 0.6
        rider = verify_rider(IdentityMode.PUBLIC_TICKET, p.credential, None)
        for name, pol in FARE_POLICIES.items():
            if p.female_free:
                rec = fare_record(f"{bus.vid}-{p.pid}", rider["rider_ref"], rider["medium"], f"S{p.origin+1:02d}", f"S{p.dest+1:02d}", dist_km, pol, 0.0, "FREE_SCHEME")
            else:
                rec = fare_record(f"{bus.vid}-{p.pid}", rider["rider_ref"], rider["medium"], f"S{p.origin+1:02d}", f"S{p.dest+1:02d}", dist_km, pol)
            fares.append((name, rec["distance_km"], rec["base_amount"], rec["amount"], len(json.dumps(rec))))
        trips.append(p)
    while bus.standing and bus.free_seat_indices():
        sp = bus.standing.pop(0)
        take_seat(bus, sp)
    boarded = 0
    lb = 0
    queue = waiting[si]
    stay = []
    for p in queue:
        if bus.load() >= SEATS + STANDING:
            stay.append(p)
            lb += 1
            continue
        if skip_decision(p, bus, si, t, scenario, shown):
            p.skips += 1
            if p.t_first_skip is None:
                p.t_first_skip = t
            stay.append(p)
            continue
        p.t_board = t
        p.bus = bus.vid
        bus.onboard[p.pid] = p
        if take_seat(bus, p):
            p.seated_at_board = True
        else:
            bus.standing.append(p)
        boarded += 1
    waiting[si] = stay
    return boarded, len(alight), lb


def sense(bus, t, cfg, default_cfg, conf, ambient):
    rng = bus.rng
    occ = np.array([o is not None for o in bus.seat_occ])
    obj = np.array([(o is not None) and (bus.seat_occ[i] is None) for i, o in enumerate(bus.seat_obj)])
    light = np.array(bus.obj_light)
    moving = bus.v > 0.5
    pressure = rng.normal(300, 150, SEATS)
    spikes = moving & (rng.random(SEATS) < 0.02)
    pressure[spikes] = rng.uniform(1200, 2000, spikes.sum())
    po = rng.normal(2600, 350, SEATS)
    drop = rng.random(SEATS) < 0.01
    po[drop] = rng.normal(900, 200, drop.sum())
    pressure = np.where(occ, po, pressure)
    pb = np.where(light, rng.normal(700, 200, SEATS), rng.normal(1900, 350, SEATS))
    pressure = np.where(obj, pb, pressure)
    pressure = np.clip(pressure, 0, 4095)
    bus.sit_time = np.where(occ, bus.sit_time + 1, 0.0)
    noise = rng.normal(0, 0.25, SEATS)

    def temps(amb):
        t_occ = bus.skin + (amb - bus.skin) * np.exp(-bus.sit_time / TAU_S)
        t_obj = amb + rng.normal(0, 0.4, SEATS)
        base = np.full(SEATS, amb)
        return np.where(occ, t_occ, np.where(obj, t_obj, base)) + noise

    tm = temps(ambient)
    for i in range(SEATS):
        p = pressure[i]
        if p < cfg.pressure_threshold:
            raw = EMPTY
        elif not cfg.temperature_check_enabled or (cfg.temp_min_c <= tm[i] <= cfg.temp_max_c):
            raw = OCCUPIED
        else:
            raw = OBJECT
        if raw == bus.debounce_state[i]:
            bus.debounce_cand[i] = raw
            bus.debounce_count[i] = 0
        else:
            if raw == bus.debounce_cand[i]:
                bus.debounce_count[i] += 1
            else:
                bus.debounce_cand[i] = raw
                bus.debounce_count[i] = 1
            if bus.debounce_count[i] >= cfg.debounce_samples:
                bus.debounce_state[i] = raw
                bus.debounce_count[i] = 0
    bus.est_states = list(bus.debounce_state)

    if t % 5 == 0:
        settled = occ & (bus.sit_time > 90)
        heavy_obj = obj & ~light
        for amb in AMBIENTS:
            ta = temps(amb)
            env = configure_for_environment(default_cfg, amb)
            for key, c in (("fixed", default_cfg), ("env", env)):
                for mask, truth in ((settled, 0), (heavy_obj, 1)):
                    idx = np.where(mask)[0]
                    for i in idx:
                        if not c.temperature_check_enabled or (c.temp_min_c <= ta[i] <= c.temp_max_c):
                            pred = 0
                        else:
                            pred = 1
                        conf[amb][key][truth, pred] += 1


def summarise(seed, scenario, passengers, arrivals_log, eta_preds, staleness, free_err_t, conf, buses_msgs, left_behind, trips, fares, wall):
    served = [p for p in passengers if p.t_board is not None]
    seekers = [p for p in served if p.wants_seat]
    actual = {}
    for a in arrivals_log:
        actual[(a["bus"], a["stop"])] = a["t"]
    eta_err = {}
    for cname, preds in eta_preds.items():
        errs = []
        for bus, si, tp, eta, age in preds:
            ta = actual.get((bus, si))
            if ta is None:
                continue
            true_eta = ta - tp
            if true_eta < 0:
                continue
            errs.append((true_eta, eta - true_eta))
        eta_err[cname] = errs
    res = {
        "seed": seed, "scenario": scenario, "wall_s": wall,
        "n_passengers": len(passengers), "n_served": len(served), "left_behind_events": left_behind,
        "seekers": len(seekers),
        "seekers_seated_at_board": sum(p.seated_at_board for p in seekers),
        "all_seated_at_board": sum(p.seated_at_board for p in served),
        "seeker_wait_s": [p.t_board - p.t_arrive for p in seekers],
        "all_wait_s": [p.t_board - p.t_arrive for p in served],
        "seeker_seat_share": [p.seat_time / max(1.0, p.seat_time + p.stand_time) for p in seekers if p.seat_time + p.stand_time > 0],
        "skips": sum(p.skips for p in served),
        "skippers": sum(1 for p in served if p.skips > 0),
        "arrivals": arrivals_log,
        "eta_err": {k: v for k, v in eta_err.items()},
        "staleness": {k: v for k, v in staleness.items()},
        "free_err_hist": np.bincount(np.clip(np.array(free_err_t) + 10, 0, 20)).tolist(),
        "conf": {str(a): {k: m.tolist() for k, m in d.items()} for a, d in conf.items()},
        "fares": fares,
        "msgs": buses_msgs,
    }
    return res


if __name__ == "__main__":
    seed = int(sys.argv[1])
    scenario = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "results")
    os.makedirs(out, exist_ok=True)
    r = run(seed, scenario, out)
    print(scenario, seed, "passengers", r["n_passengers"], "served", r["n_served"], "wall", round(r["wall_s"], 1))
