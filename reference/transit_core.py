import hashlib
import json
import math
from dataclasses import dataclass, field, asdict
from enum import Enum


EMPTY = "EMPTY"
OBJECT = "OBJECT"
OCCUPIED = "OCCUPIED"


@dataclass
class SeatConfig:
    pressure_threshold: int = 1200
    temp_min_c: float = 34.0
    temp_max_c: float = 42.0
    debounce_samples: int = 3
    ambient_margin_c: float = 2.0
    skin_floor_c: float = 33.0
    temperature_check_enabled: bool = True

    def validate(self):
        if not 0 < self.pressure_threshold < 4095:
            raise ValueError("pressure_threshold must lie inside the 12-bit ADC range")
        if self.temp_min_c >= self.temp_max_c:
            raise ValueError("temp_min_c must be below temp_max_c")
        if self.debounce_samples < 1:
            raise ValueError("debounce_samples must be at least 1")
        return self


def configure_for_environment(cfg, ambient_c):
    out = SeatConfig(**asdict(cfg))
    lower = ambient_c + out.ambient_margin_c
    if lower > out.skin_floor_c:
        out.temperature_check_enabled = False
        return out
    out.temp_min_c = lower
    out.temperature_check_enabled = True
    return out


def classify_seat(pressure, temperature_c, cfg):
    if pressure < cfg.pressure_threshold:
        return EMPTY
    if not cfg.temperature_check_enabled:
        return OCCUPIED
    if cfg.temp_min_c <= temperature_c <= cfg.temp_max_c:
        return OCCUPIED
    return OBJECT


class SeatDebouncer:
    def __init__(self, cfg, initial=EMPTY):
        self.cfg = cfg
        self.state = initial
        self.candidate = initial
        self.count = 0

    def update(self, raw_state):
        if raw_state == self.state:
            self.candidate = raw_state
            self.count = 0
            return self.state
        if raw_state == self.candidate:
            self.count += 1
        else:
            self.candidate = raw_state
            self.count = 1
        if self.count >= self.cfg.debounce_samples:
            self.state = raw_state
            self.count = 0
        return self.state


def free_seat_count(states):
    return sum(1 for s in states if s == EMPTY)


def parse_nmea_rmc(sentence):
    body = sentence.strip()
    if not body.startswith("$") or "*" not in body:
        raise ValueError("not an NMEA sentence")
    data, checksum = body[1:].split("*", 1)
    calc = 0
    for ch in data:
        calc ^= ord(ch)
    if f"{calc:02X}" != checksum[:2].upper():
        raise ValueError("NMEA checksum mismatch")
    parts = data.split(",")
    if not parts[0].endswith("RMC"):
        raise ValueError("not an RMC sentence")
    if parts[2] != "A":
        return None
    lat = int(parts[3][:2]) + float(parts[3][2:]) / 60.0
    if parts[4] == "S":
        lat = -lat
    lon = int(parts[5][:3]) + float(parts[5][3:]) / 60.0
    if parts[6] == "W":
        lon = -lon
    speed_mps = float(parts[7] or 0.0) * 0.514444
    return {"lat": lat, "lon": lon, "speed_mps": speed_mps}


def build_nmea_rmc(lat, lon, speed_mps, hhmmss="120000.00", ddmmyy="161026"):
    lat_h = "N" if lat >= 0 else "S"
    lon_h = "E" if lon >= 0 else "W"
    alat, alon = abs(lat), abs(lon)
    lat_s = f"{int(alat):02d}{(alat - int(alat)) * 60:07.4f}"
    lon_s = f"{int(alon):03d}{(alon - int(alon)) * 60:07.4f}"
    knots = speed_mps / 0.514444
    data = f"GPRMC,{hhmmss},A,{lat_s},{lat_h},{lon_s},{lon_h},{knots:.2f},0.0,{ddmmyy},,,A"
    calc = 0
    for ch in data:
        calc ^= ord(ch)
    return f"${data}*{calc:02X}"


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


STATIONARY_SPEED_MPS = 0.5
STATIONARY_DISPLACEMENT_M = 3.0


def is_stationary(prev_fix, cur_fix):
    if prev_fix is None or cur_fix is None:
        return False
    moved = haversine_m(prev_fix["lat"], prev_fix["lon"], cur_fix["lat"], cur_fix["lon"])
    return moved < STATIONARY_DISPLACEMENT_M and cur_fix["speed_mps"] < STATIONARY_SPEED_MPS


def boarding_allowed(stationary, door_open):
    return bool(stationary and door_open)


class IdentityMode(str, Enum):
    INSTITUTIONAL_FACE = "INSTITUTIONAL_FACE"
    PUBLIC_TICKET = "PUBLIC_TICKET"


PUBLIC_MEDIA = ("NCMC", "QR", "ETM", "PASS")


def rider_reference(raw_id, salt):
    return hashlib.sha256(f"{salt}:{raw_id}".encode()).hexdigest()[:16]


def verify_rider(mode, credential, lookup, salt="deployment-salt"):
    if mode == IdentityMode.INSTITUTIONAL_FACE:
        member_id = lookup(credential)
        if member_id is None:
            return {"ok": False, "medium": "FACE", "rider_ref": None}
        return {"ok": True, "medium": "FACE", "rider_ref": rider_reference(member_id, salt)}
    medium, _, token = credential.partition(":")
    if medium not in PUBLIC_MEDIA or not token:
        return {"ok": False, "medium": medium or None, "rider_ref": None}
    if lookup is not None and not lookup(credential):
        return {"ok": False, "medium": medium, "rider_ref": None}
    return {"ok": True, "medium": medium, "rider_ref": rider_reference(token, salt)}


@dataclass
class FarePolicy:
    kind: str
    currency: str = "INR"
    rate_per_km: float = 0.0
    minimum: float = 0.0
    slabs: list = field(default_factory=list)
    stage_length_km: float = 2.0
    stage_fares: list = field(default_factory=list)
    flat_amount: float = 0.0
    rounding: float = 1.0
    name: str = ""


def per_km_policy(rate=5.0, minimum=2.0, name="per-km"):
    return FarePolicy(kind="PER_KM", rate_per_km=rate, minimum=minimum, rounding=0.01, name=name)


def slab_policy(slabs, name="distance-slab"):
    return FarePolicy(kind="DISTANCE_SLAB", slabs=list(slabs), name=name)


def stage_policy(stage_length_km, stage_fares, name="stage"):
    return FarePolicy(kind="STAGE", stage_length_km=stage_length_km, stage_fares=list(stage_fares), name=name)


def flat_policy(amount, name="flat"):
    return FarePolicy(kind="FLAT", flat_amount=amount, name=name)


def _round_to(value, step):
    return round(round(value / step) * step, 2)


def base_fare(policy, distance_km):
    if distance_km < 0:
        raise ValueError("distance cannot be negative")
    if policy.kind == "PER_KM":
        return _round_to(max(policy.minimum, distance_km * policy.rate_per_km), policy.rounding)
    if policy.kind == "DISTANCE_SLAB":
        for upper_km, amount in policy.slabs:
            if distance_km <= upper_km:
                return float(amount)
        return float(policy.slabs[-1][1])
    if policy.kind == "STAGE":
        stages = max(1, math.ceil(distance_km / policy.stage_length_km - 1e-9))
        idx = min(stages, len(policy.stage_fares)) - 1
        return float(policy.stage_fares[idx])
    if policy.kind == "FLAT":
        return float(policy.flat_amount)
    raise ValueError(f"unknown fare policy {policy.kind}")


def stages_travelled(policy, distance_km):
    if policy.kind != "STAGE":
        return None
    return max(1, math.ceil(distance_km / policy.stage_length_km - 1e-9))


def fare_record(trip_id, rider_ref, medium, origin_stop, dest_stop, distance_km, policy, concession=1.0, concession_label="STANDARD"):
    base = base_fare(policy, distance_km)
    amount = round(base * concession, 2)
    return {
        "schema": "fare-record/1.0",
        "trip_id": trip_id,
        "rider_ref": rider_ref,
        "payment_medium": medium,
        "origin_stop": origin_stop,
        "destination_stop": dest_stop,
        "distance_km": round(distance_km, 3),
        "stages": stages_travelled(policy, distance_km),
        "policy_kind": policy.kind,
        "policy_name": policy.name,
        "base_amount": base,
        "concession": concession_label,
        "amount": amount,
        "currency": policy.currency,
    }


def route_distance_km(fixes):
    total = 0.0
    for a, b in zip(fixes, fixes[1:]):
        total += haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    return total / 1000.0


class EtaEstimator:
    def __init__(self, alpha=0.2, speed_floor_mps=1.5, dwell_s=20.0, default_speed_mps=6.0):
        self.alpha = alpha
        self.speed_floor = speed_floor_mps
        self.dwell_s = dwell_s
        self.speed = default_speed_mps

    def observe(self, distance_m, elapsed_s):
        if elapsed_s <= 0:
            return self.speed
        v = distance_m / elapsed_s
        self.speed = self.alpha * v + (1 - self.alpha) * self.speed
        return self.speed

    def eta_s(self, remaining_m, stops_between):
        return remaining_m / max(self.speed, self.speed_floor) + self.dwell_s * max(0, stops_between)


FEW_SEATS_LIMIT = 5
STALE_AFTER_S = 60


def seat_label(free_seats):
    if free_seats <= 0:
        return "NO SEATS"
    if free_seats <= FEW_SEATS_LIMIT:
        return "FEW SEATS"
    return "SEATS AVAILABLE"


def build_stop_board(stop_id, stop_name, arrivals, now_s, max_rows=4):
    rows = []
    for a in sorted(arrivals, key=lambda r: r["eta_s"])[:max_rows]:
        age = now_s - a["updated_s"]
        rows.append({
            "route": a["route"],
            "bus": a["bus"],
            "eta_min": max(0, int(round(a["eta_s"] / 60.0))),
            "free_seats": int(a["free_seats"]),
            "label": seat_label(int(a["free_seats"])),
            "approximate": age > STALE_AFTER_S,
            "data_age_s": int(age),
        })
    return {"schema": "stop-board/1.0", "stop_id": stop_id, "stop_name": stop_name, "generated_s": int(now_s), "rows": rows}


def build_seat_summary(bus_id, route, seq, fix, states, door_open, ts_s):
    return {
        "schema": "seat-summary/1.0",
        "bus": bus_id,
        "route": route,
        "seq": seq,
        "ts": int(ts_s),
        "lat": round(fix["lat"], 6),
        "lon": round(fix["lon"], 6),
        "speed_mps": round(fix["speed_mps"], 2),
        "seats_total": len(states),
        "free_seats": free_seat_count(states),
        "objects": sum(1 for s in states if s == OBJECT),
        "occupied": sum(1 for s in states if s == OCCUPIED),
        "door_open": bool(door_open),
    }


def encode(payload):
    return json.dumps(payload, separators=(",", ":"))


def build_sms_summary(summary):
    return f"B{summary['bus']}|R{summary['route']}|S{summary['seq']}|F{summary['free_seats']}|{summary['lat']:.5f},{summary['lon']:.5f}|T{summary['ts']}"


T1, T2, T3 = "T1", "T2", "T3"
RECIPIENT = {T1: "LOG_ONLY", T2: "CONTROL_ROOM", T3: "CONTROL_ROOM_AND_MAINTENANCE"}
SILENT_LIMIT_S = 120
FAULTY_SEAT_LIMIT = 5
TICKET_MISMATCH_LIMIT = 5


def assess_event(ev):
    if ev.get("door_open_while_moving") or (ev.get("boarding_registered") and not ev.get("stationary_at_event", True)):
        return {"tier": T3, "reason": "boarding or door-open while moving", "recipient": RECIPIENT[T3]}
    if ev.get("faulty_seats", 0) >= FAULTY_SEAT_LIMIT:
        return {"tier": T3, "reason": "sensor fault across many seats", "recipient": RECIPIENT[T3]}
    if ev.get("rider_rejected_but_entered"):
        return {"tier": T3, "reason": "rider failed verification but entry recorded", "recipient": RECIPIENT[T3]}
    if ev.get("occupied_seats", 0) - ev.get("validated_tickets", 0) >= TICKET_MISMATCH_LIMIT:
        return {"tier": T2, "reason": "seat-state versus ticket mismatch", "recipient": RECIPIENT[T2]}
    if ev.get("gps_jump"):
        return {"tier": T2, "reason": "fare distance implausible (GNSS jump)", "recipient": RECIPIENT[T2]}
    if ev.get("silent_s", 0) > SILENT_LIMIT_S:
        return {"tier": T2, "reason": "bus silent beyond limit", "recipient": RECIPIENT[T2]}
    if ev.get("entry_exit_unpaired"):
        return {"tier": T2, "reason": "entry without matching exit", "recipient": RECIPIENT[T2]}
    return {"tier": T1, "reason": "consistent", "recipient": RECIPIENT[T1]}
