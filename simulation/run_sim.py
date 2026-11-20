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

from build_scenario import build, SIM_END, STOP_POS, STOP_LEN, SHARED
from transit_core import (
    SeatConfig, configure_for_environment, EMPTY, OBJECT, OCCUPIED, build_seat_summary, encode,
    ThermalConfig, differential_classify, FilterConfig,
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
BETA_0 = float(os.environ.get("BETA_0", "0.0"))
BETA_WAIT = float(os.environ.get("BETA_WAIT", "-0.35"))
BETA_SEAT = float(os.environ.get("BETA_SEAT", "2.0"))
BETA_CROWD = float(os.environ.get("BETA_CROWD", "1.0"))
BETA_WAITED = float(os.environ.get("BETA_WAITED", "-0.2"))
KAPPA_EXPOSURE = float(os.environ.get("KAPPA_EXPOSURE", "0.5"))
SHELTER_SHARE = float(os.environ.get("SHELTER_SHARE", "0.5"))
DWELL_BASE, DWELL_BOARD, DWELL_ALIGHT = 10.0, 2.0, 1.5
PUBLISH_EVERY = 10
SMS_MODE = os.environ.get("SMS_MODE", "event")
SMS_EVERY = 30
SMS_DELTA = 2
SMS_KEEPALIVE = 300
FILTER_MODE = os.environ.get("FILTER_MODE", "filtered")
FCFG = FilterConfig().validate()
SUBSAMPLES = int(FCFG.sample_hz)
SHOCKS_PER_S = 2.0 / 60.0
VIB_RMS = 0.7
BRANCH_RATE_PER_MIN = 1.0
BRANCH_DEST_SHARE = 0.15
BOARD_EVERY = 10
DISPLAY_LAG = 1
WEAK_EDGES = {6}
DEAD_EDGES = {13}
OUTAGE_RATE = 1 / float(os.environ.get("OUTAGE_EVERY_S", "1800"))
OUTAGE_MEAN_S = 60
MAIN_AMBIENT = 31.0
AMBIENTS = [22.0, 25.0, 28.0, 30.0, 31.0, 32.0, 33.0, 34.0, 35.0, 36.0, 37.0, 38.0, 40.0, 42.0]
AMBIENTS_V1 = {22.0, 25.0, 28.0, 30.0, 31.0, 32.0, 34.0, 36.0, 38.0, 40.0}
SKIN_PULL = 0.15
BAG_TAU_S = 600.0
BAG_INIT_SD = 3.0
THERMAL_CFG = ThermalConfig()
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
    __slots__ = ("pid", "origin", "dest", "t_arrive", "wants_seat", "t_board", "seated_at_board",
                 "seat_time", "stand_time", "skips", "t_first_skip", "bus", "credential", "female_free", "routes", "route")

    def __init__(self, pid, origin, dest, t, rng, routes=("21",)):
        self.pid = pid
        self.routes = routes
        self.route = None
        self.origin = origin
        self.dest = dest
        self.t_arrive = t
        self.wants_seat = rng.random() < SEEK_PROB
        rng.uniform(120.0, 780.0)
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
    def __init__(self, vid, rng, route="21"):
        self.vid = vid
        self.route = route
        self.k = -1
        self.dnext = 0.0
        self.win = np.full((FCFG.median_window, SEATS), 300.0)
        self.widx = 0
        self.ema = np.full(SEATS, 300.0)
        self.base = np.zeros(SEATS)
        self.loaded = np.zeros(SEATS, dtype=bool)
        self.lvl = np.full(SEATS, 2600.0)
        self.db_state = np.zeros(SEATS, dtype=bool)
        self.db_cand = np.zeros(SEATS, dtype=bool)
        self.db_count = np.zeros(SEATS, dtype=int)
        self.th_state = [OCCUPIED] * SEATS
        self.last_sms_free = None
        self.sms_door_due = False
        self.seat_occ = [None] * SEATS
        self.seat_obj = [None] * SEATS
        self.obj_light = [False] * SEATS
        self.sit_time = np.zeros(SEATS)
        self.skin = np.full(SEATS, 35.3)
        self.obj_time = np.zeros(SEATS)
        self.obj_init = np.zeros(SEATS)
        self.rng2 = np.random.default_rng(rng.bit_generator.seed_seq.spawn(1)[0])
        self.rng3 = np.random.default_rng(rng.bit_generator.seed_seq.spawn(1)[0])
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
        self.msgs = {"primary": 0, "sms": 0, "bytes_primary": 0, "bytes_sms": 0, "buffered": 0, "route": route}
        self.rng = rng
        self.age = 0

    def load(self):
        return len(self.onboard)

    def gt_free(self):
        return sum(1 for i in range(SEATS) if self.seat_occ[i] is None and self.seat_obj[i] is None)

    def free_seat_indices(self):
        return [i for i in range(SEATS) if self.seat_occ[i] is None and self.seat_obj[i] is None]


class Cloud:
    def __init__(self, name, lines, stop_names):
        self.name = name
        self.state = {}
        self.lines = lines
        self.stop_names = stop_names
        self.boards = {}
        self.seg_time = {}
        for r, d in lines.items():
            sd = d["stopdist"]
            self.seg_time[r] = [(sd[k] - (sd[k - 1] if k else 0.0)) / 6.0 + 25.0 for k in range(len(sd))]
        self.last_stop = {}

    def receive(self, rep):
        b = rep["bus"]
        prev = self.state.get(b)
        if prev and rep["ts"] <= prev["ts"]:
            return
        r = rep["route"]
        s = rep["k"]
        ls = self.last_stop.get(b)
        if ls is None or s > ls[0]:
            if ls is not None and s == ls[0] + 1 and s >= 1:
                seg = rep["ts"] - ls[1]
                if 20 < seg < 1800:
                    self.seg_time[r][s] = 0.5 * seg + 0.5 * self.seg_time[r][s]
            self.last_stop[b] = (s, rep["ts"])
        self.state[b] = rep

    def drop(self, b):
        self.state.pop(b, None)
        self.last_stop.pop(b, None)

    def eta(self, r, g, now):
        line = self.lines[r["route"]]
        if g not in line["stops"]:
            return None
        kt = line["stops"].index(g)
        nxt = r["k"] + 1
        if nxt > kt:
            return None
        sd = line["stopdist"]
        span = max(1.0, sd[nxt] - (sd[nxt - 1] if nxt else 0.0))
        frac = min(1.0, max(0.0, r["dnext"] / span))
        st = self.seg_time[r["route"]]
        rem = max(0.0, st[nxt] * frac - (now - r["ts"]))
        for k in range(nxt + 1, kt + 1):
            rem += st[k]
        return rem

    def make_boards(self, now):
        out = {}
        for g, name in enumerate(self.stop_names):
            arrivals = []
            for b, r in self.state.items():
                e = self.eta(r, g, now)
                if e is None:
                    continue
                arrivals.append({"route": r["route"], "bus": b, "eta_s": e, "free_seats": r["free"], "updated_s": r["ts"]})
            out[g] = build_stop_board(name, f"Stop {name}", arrivals, now)
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
    lines = sc["lines"]
    stop_names = sc["stop_names"]
    nstops = len(stop_names)
    ncorr = len(edges)
    route_of = {"line21": "21", "line22": "22"}
    pos_in = {r: {g: i for i, g in enumerate(d["stops"])} for r, d in lines.items()}
    cfg = configure_for_environment(SeatConfig().validate(), ambient)
    default_cfg = SeatConfig().validate()
    cmd = [os.path.join(sumo.SUMO_HOME, "bin", "sumo"), "-n", sc["net"], "-a", sc["stops"],
           "-r", ",".join(sc["routes"]), "--step-length", "1", "--no-step-log", "true",
           "--no-warnings", "true", "--seed", str(seed), "--time-to-teleport", "300",
           "--end", str(SIM_END)]
    traci.start(cmd)

    clouds = {k: Cloud(k, lines, stop_names) for k in ("fallback", "primary_only", "oracle")}
    shown = {k: {} for k in clouds}
    display_queue = {k: None for k in clouds}
    msg_stats = []
    tiebreak = 0
    pending = []
    waiting = [[] for _ in range(nstops)]
    passengers = []
    shelter = np.random.default_rng(seed + 7777).random(nstops) < SHELTER_SHARE
    buses = {}
    pid = 0
    arrivals_log = []
    eta_preds = defaultdict(list)
    staleness = {k: [] for k in clouds}
    free_err_t = []
    conf = {a: {k: np.zeros((2, 2), dtype=np.int64) for k in ("fixed", "env", "diff")} for a in AMBIENTS}
    blind = {a: 0 for a in AMBIENTS}
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

        if 300 <= t <= SIM_END - 1200:
            for si in range(ncorr):
                lam = ARRIVAL_PER_MIN[si] / 60.0
                if lam <= 0:
                    continue
                for _ in range(demand_rng.poisson(lam)):
                    k = 1 + demand_rng.poisson(5)
                    if si in SHARED and demand_rng.random() < BRANCH_DEST_SHARE:
                        dest = lines["22"]["stops"][-1 - int(demand_rng.integers(0, 2))]
                    else:
                        dest = min(ncorr - 1, si + k)
                    if dest == si:
                        continue
                    rs = feasible_routes(lines, pos_in, si, dest)
                    if not rs:
                        continue
                    p = Passenger(pid, si, dest, t, demand_rng, rs)
                    pid += 1
                    passengers.append(p)
                    waiting[si].append(p)
            seq22 = lines["22"]["stops"]
            for j in (0, 1):
                g = seq22[j]
                lam = BRANCH_RATE_PER_MIN * DEMAND_SCALE / 60.0
                for _ in range(demand_rng.poisson(lam)):
                    dest = seq22[min(len(seq22) - 1, j + 1 + demand_rng.poisson(5))]
                    rs = feasible_routes(lines, pos_in, g, dest)
                    p = Passenger(pid, g, dest, t, demand_rng, rs)
                    pid += 1
                    passengers.append(p)
                    waiting[g].append(p)

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
                buses[vid] = Bus(vid, np.random.default_rng(rng.integers(1 << 30)), route_of[traci.vehicle.getRouteID(vid)])

        for vid, bus in buses.items():
            x, y = traci.vehicle.getPosition(vid)
            v = traci.vehicle.getSpeed(vid)
            road = traci.vehicle.getRoadID(vid)
            edge_idx = edges.index(road) if road in edges else -1
            lat, lon = to_latlon(x, y)
            fix = parse_nmea_rmc(build_nmea_rmc(lat, lon, v))
            bus.x, bus.v = x, v
            bus.age += 1
            if t % 10 == 0:
                traj.append((vid, t, round(x, 1), bus.load(), bus.gt_free()))

            line = lines[bus.route]
            if bus.dwell_until is None and traci.vehicle.isStopped(vid):
                stops = traci.vehicle.getStops(vid, 1)
                if stops and stops[0].arrival >= 0 and stops[0].stoppingPlaceID in stop_names:
                    si = stop_names.index(stops[0].stoppingPlaceID)
                    kk = pos_in[bus.route].get(si, -1)
                    if kk > bus.k:
                        arrivals_log.append(arrival_record(bus, si, t, clouds, shown))
                        nb, na, lb = serve_stop(bus, si, t, waiting, scenario, shown, rng, trips, fares, shelter[si], line)
                        left_behind += lb
                        bus.dwell_until = t + DWELL_BASE + DWELL_BOARD * nb + DWELL_ALIGHT * na
                        bus.door_open = True
                        bus.served = si
                        bus.k = kk
            elif bus.dwell_until is not None and t >= bus.dwell_until:
                bus.dwell_until = None
                bus.door_open = False
                bus.last_pub = -999
                bus.sms_door_due = True
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

            nk = bus.k + 1
            if nk < len(line["stops"]):
                try:
                    tgt = traci.busstop.getLaneID(stop_names[line["stops"][nk]]).rsplit("_", 1)[0]
                    d = traci.vehicle.getDrivingDistance(vid, tgt, STOP_POS + STOP_LEN / 2)
                    bus.dnext = d if d >= 0 else 0.0
                except Exception:
                    bus.dnext = 0.0
            else:
                bus.dnext = 0.0
            sense(bus, t, cfg, default_cfg, conf, ambient, blind)
            est_free = sum(1 for s in bus.est_states if s == EMPTY)
            gt = bus.gt_free()
            free_err_t.append(est_free - gt)

            orep = {"bus": vid, "route": bus.route, "dnext": bus.dnext, "free": gt, "ts": t, "k": bus.k}
            clouds["oracle"].receive(orep)

            mode = link_mode(bus, edge_idx, t)
            due_primary = (t - bus.last_pub) >= PUBLISH_EVERY
            if due_primary:
                bus.seq += 1
                summ = build_seat_summary(vid, bus.route, bus.seq, fix, bus.est_states, bus.door_open, t)
                rep = {"bus": vid, "route": bus.route, "dnext": bus.dnext, "free": summ["free_seats"], "ts": t, "k": bus.k}
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
                    if mode == "sms" and sms_due(bus, summ["free_seats"], t):
                        bus.last_sms = t
                        bus.last_sms_free = summ["free_seats"]
                        bus.sms_door_due = False
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
    result["blind"] = {str(a): v for a, v in blind.items()}
    result["shelter"] = shelter.astype(int).tolist()
    result["params"] = {"BETA_0": BETA_0, "BETA_WAIT": BETA_WAIT, "BETA_SEAT": BETA_SEAT, "BETA_CROWD": BETA_CROWD,
                        "BETA_WAITED": BETA_WAITED, "KAPPA_EXPOSURE": KAPPA_EXPOSURE, "SEEK_PROB": SEEK_PROB,
                        "DEMAND_SCALE": DEMAND_SCALE, "OUTAGE_RATE": OUTAGE_RATE, "SMS_MODE": SMS_MODE,
                        "FILTER_MODE": FILTER_MODE}
    result["lines"] = {r: {"stops": d["stops"], "stopdist": d["stopdist"], "length_m": d["length_m"]} for r, d in lines.items()}
    result["stop_names"] = stop_names
    result["traj"] = traj
    result["snapshots"] = snapshots
    with open(os.path.join(out_dir, f"result_{scenario}_{seed}.json"), "w") as f:
        json.dump(result, f)
    return result


def feasible_routes(lines, pos_in, o, d):
    out = []
    for r in lines:
        po, pd = pos_in[r].get(o), pos_in[r].get(d)
        if po is not None and pd is not None and pd > po:
            out.append(r)
    return tuple(out)


def sms_due(bus, free, t):
    if SMS_MODE == "timer":
        return (t - bus.last_sms) >= SMS_EVERY
    if bus.sms_door_due:
        return True
    if bus.last_sms_free is None:
        return True
    if abs(free - bus.last_sms_free) >= SMS_DELTA or ((free == 0) != (bus.last_sms_free == 0)):
        return True
    return (t - bus.last_sms) >= SMS_KEEPALIVE


def display_for(shown, cname, si):
    s = shown.get(cname, {})
    boards = s.get("boards")
    if not boards:
        return None
    return boards.get(si)


def arrival_record(bus, si, t, clouds, shown):
    rec = {"bus": bus.vid, "route": bus.route, "stop": si, "t": t, "gt_free": bus.gt_free(), "load": bus.load()}
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


def wait_utility(eta_min, p_seat_next, load_frac, waited_min, sheltered):
    exposure = 1.0 + (0.0 if sheltered else KAPPA_EXPOSURE)
    return (BETA_0 + BETA_WAIT * exposure * eta_min + BETA_SEAT * p_seat_next
            + BETA_CROWD * load_frac + BETA_WAITED * waited_min)


def skip_decision(p, bus, si, t, scenario, shown, rng, sheltered, seekers_waiting):
    if bus.route not in p.routes:
        return False
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
        elif row["route"] in p.routes:
            later.append(row)
    if this_row is None or this_row["free_seats"] > 0:
        return False
    best = None
    for row in later:
        if row["free_seats"] > 0 and row["eta_min"] > 0:
            if best is None or row["eta_min"] < best["eta_min"]:
                best = row
    if best is None:
        return False
    p_seat = min(1.0, best["free_seats"] / max(1, seekers_waiting))
    load_frac = bus.load() / float(SEATS + STANDING)
    waited = (t - p.t_first_skip) / 60.0 if p.t_first_skip is not None else 0.0
    u = wait_utility(best["eta_min"], p_seat, load_frac, waited, sheltered)
    p_wait = 1.0 / (1.0 + math.exp(-u))
    return rng.random() < p_wait


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
            bus.obj_time[j] = 0.0
            bus.obj_init[j] = bus.rng2.normal(0.0, BAG_INIT_SD)
    return True


def serve_stop(bus, si, t, waiting, scenario, shown, rng, trips, fares, sheltered=True, line=None):
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
        po, pd = line["stops"].index(p.origin), line["stops"].index(p.dest)
        dist_km = (line["stopdist"][pd] - line["stopdist"][po]) / 1000.0
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
    seekers_waiting = sum(1 for q in queue if q.wants_seat and bus.route in q.routes)
    stay = []
    for p in queue:
        if bus.route not in p.routes:
            stay.append(p)
            continue
        if bus.load() >= SEATS + STANDING:
            stay.append(p)
            lb += 1
            continue
        if skip_decision(p, bus, si, t, scenario, shown, rng, sheltered, seekers_waiting):
            p.skips += 1
            if p.t_first_skip is None:
                p.t_first_skip = t
            stay.append(p)
            continue
        p.t_board = t
        p.bus = bus.vid
        p.route = bus.route
        bus.onboard[p.pid] = p
        if take_seat(bus, p):
            p.seated_at_board = True
        else:
            bus.standing.append(p)
        boarded += 1
    waiting[si] = stay
    return boarded, len(alight), lb


def sense(bus, t, cfg, default_cfg, conf, ambient, blind):
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
    bus.obj_time = np.where(obj, bus.obj_time + 1, 0.0)
    noise = rng.normal(0, 0.25, SEATS)
    rng2 = bus.rng2

    def temps_v1(amb):
        t_occ = bus.skin + (amb - bus.skin) * np.exp(-bus.sit_time / TAU_S)
        t_obj = amb + rng.normal(0, 0.4, SEATS)
        base = np.full(SEATS, amb)
        return np.where(occ, t_occ, np.where(obj, t_obj, base)) + noise

    def temps(amb, lag=0.0, noise_sd=0.25):
        contact = bus.skin + SKIN_PULL * (amb - bus.skin)
        st = np.maximum(bus.sit_time - lag, 0.0)
        ot = np.maximum(bus.obj_time - lag, 0.0)
        t_occ = contact + (amb - contact) * np.exp(-st / TAU_S)
        t_obj = amb + bus.obj_init * np.exp(-ot / BAG_TAU_S)
        base = np.full(SEATS, amb)
        out = np.where(occ, t_occ, np.where(obj, t_obj, base))
        return out + rng2.normal(0, noise_sd, SEATS)

    if FILTER_MODE == "legacy_model":
        tm = temps_v1(ambient)
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
    else:
        filtered_states(bus, occ, obj, light, moving, t, ambient, temps)

    if t % 5 == 0:
        settled = occ & (bus.sit_time > 90)
        heavy_obj = obj & ~light & (bus.obj_time > 90)
        lag = np.minimum(np.where(occ, bus.sit_time, bus.obj_time), THERMAL_CFG.window_s)
        for amb in AMBIENTS:
            if amb in AMBIENTS_V1:
                rng.normal(0, 0.4, SEATS)
            sd5 = 0.25 / math.sqrt(THERMAL_CFG.smooth_n)
            ta = temps(amb, 0.0, sd5)
            tb = temps(amb, lag, sd5)
            env = configure_for_environment(default_cfg, amb)
            cabin = amb + rng2.normal(0, sd5, SEATS)
            for key, c in (("fixed", default_cfg), ("env", env), ("diff", None)):
                for mask, truth in ((settled, 0), (heavy_obj, 1)):
                    for i in np.where(mask)[0]:
                        if key == "diff":
                            state, flag = differential_classify(ta[i] - cabin[i], tb[i] - cabin[i], ta[i], cabin[i], THERMAL_CFG)
                            pred = 0 if state == OCCUPIED else 1
                            if flag == "blind":
                                blind[amb] += 1
                        elif not c.temperature_check_enabled or (c.temp_min_c <= ta[i] <= c.temp_max_c):
                            pred = 0
                        else:
                            pred = 1
                        conf[amb][key][truth, pred] += 1


def filtered_states(bus, occ, obj, light, moving, t, ambient, temps):
    rng = bus.rng3
    n = SEATS
    fresh_occ = occ & (bus.sit_time == 1)
    fresh_obj = obj & (bus.obj_time == 1)
    bus.lvl = np.where(fresh_occ, rng.normal(2600, 350, n), bus.lvl)
    bus.lvl = np.where(fresh_obj, np.where(light, rng.normal(700, 200, n), rng.normal(1900, 350, n)), bus.lvl)
    level = np.where(occ | obj, np.clip(bus.lvl, 0, 4095), 300.0)
    shock = np.zeros(SUBSAMPLES)
    if moving and rng.random() < SHOCKS_PER_S:
        m = int(rng.integers(1, 3))
        i0 = int(rng.integers(0, SUBSAMPLES - m + 1))
        peak = rng.uniform(0.4, 1.4) * rng.choice([-1.0, 1.0])
        shock[i0:i0 + m] = peak * np.sin(math.pi * (np.arange(m) + 0.5) / m)
    a = FCFG.ema_alpha
    was_loaded = bus.loaded.copy()
    first = None
    for k in range(SUBSAMPLES):
        g = 1.0 + (rng.normal(0, VIB_RMS) / 9.81 if moving else 0.0) + shock[k]
        x = np.where(occ | obj, level * min(max(g, 0.0), 3.0), level) + rng.normal(0, 25, n)
        x = np.clip(x, 0, 4095)
        if first is None:
            first = x.copy()
        bus.win[bus.widx] = x
        bus.widx = (bus.widx + 1) % FCFG.median_window
        med = np.median(bus.win, axis=0)
        bus.ema = a * med + (1 - a) * bus.ema
        net = bus.ema - bus.base
        bus.loaded = np.where(bus.loaded, net >= FCFG.exit_counts, net >= FCFG.enter_counts)
        idle = ~bus.loaded
        bus.base = np.where(idle, np.clip(bus.base + FCFG.baseline_rate * (bus.ema - bus.base), 0.0, FCFG.baseline_cap), bus.base)
    if FILTER_MODE == "debounce":
        raw = first >= FCFG.enter_counts
        agree = raw == bus.db_cand
        bus.db_count = np.where(raw == bus.db_state, 0, np.where(agree, bus.db_count + 1, 1))
        bus.db_cand = raw
        flip = bus.db_count >= 3
        bus.db_state = np.where(flip, raw, bus.db_state)
        bus.db_count = np.where(flip, 0, bus.db_count)
        bus.loaded = bus.db_state.copy()
    newly = bus.loaded & ~was_loaded
    for i in np.where(newly)[0]:
        bus.th_state[i] = OCCUPIED
    if t % 5 == 0 and bus.loaded.any():
        idx = np.where(bus.loaded)[0]
        lag = np.minimum(np.where(occ, bus.sit_time, bus.obj_time), THERMAL_CFG.window_s)
        sd5 = 0.25 / math.sqrt(THERMAL_CFG.smooth_n)
        contact = bus.skin + SKIN_PULL * (ambient - bus.skin)
        base_t = []
        for lg in (0.0, lag):
            st_ = np.maximum(bus.sit_time - lg, 0.0)
            ot_ = np.maximum(bus.obj_time - lg, 0.0)
            t_occ = contact + (ambient - contact) * np.exp(-st_ / TAU_S)
            t_obj = ambient + bus.obj_init * np.exp(-ot_ / BAG_TAU_S)
            base_t.append(np.where(occ, t_occ, np.where(obj, t_obj, ambient)) + rng.normal(0, sd5, n))
        ta, tb = base_t
        cabin = ambient + rng.normal(0, sd5)
        for i in idx:
            if not (occ[i] or obj[i]):
                continue
            st, _ = differential_classify(ta[i] - cabin, tb[i] - cabin, ta[i], cabin, THERMAL_CFG)
            bus.th_state[i] = st
    bus.est_states = [bus.th_state[i] if bus.loaded[i] else EMPTY for i in range(n)]


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
