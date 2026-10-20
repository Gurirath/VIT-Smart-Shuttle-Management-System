import math
import pytest

from transit_core import (
    SeatConfig, classify_seat, configure_for_environment, SeatDebouncer, free_seat_count,
    EMPTY, OBJECT, OCCUPIED, parse_nmea_rmc, build_nmea_rmc, haversine_m, is_stationary,
    boarding_allowed, IdentityMode, verify_rider, per_km_policy, slab_policy, stage_policy,
    flat_policy, base_fare, fare_record, EtaEstimator, build_stop_board, seat_label,
    build_seat_summary, build_sms_summary, encode,
)

DEFAULT = SeatConfig().validate()

BOUNDARY_CASES = [
    (1199, 36.7, EMPTY),
    (1200, 36.7, OCCUPIED),
    (2600, 33.9, OBJECT),
    (2600, 34.0, OCCUPIED),
    (2600, 42.0, OCCUPIED),
    (2600, 42.1, OBJECT),
    (2600, 39.5, OCCUPIED),
]


@pytest.mark.parametrize("pressure,temp,expected", BOUNDARY_CASES)
def test_default_band_boundaries(pressure, temp, expected):
    assert classify_seat(pressure, temp, DEFAULT) == expected


def test_operator_band_override():
    cfg = SeatConfig(temp_min_c=30.0, temp_max_c=40.0).validate()
    assert classify_seat(2600, 31.0, cfg) == OCCUPIED
    assert classify_seat(2600, 29.9, cfg) == OBJECT
    assert classify_seat(2600, 40.1, cfg) == OBJECT


def test_hot_environment_falls_back_to_pressure_only():
    hot = configure_for_environment(DEFAULT, ambient_c=36.0)
    assert hot.temperature_check_enabled is False
    assert classify_seat(2600, 36.0, hot) == OCCUPIED
    assert classify_seat(1000, 36.0, hot) == EMPTY
    edge = configure_for_environment(DEFAULT, ambient_c=31.1)
    assert edge.temperature_check_enabled is False


def test_mild_environment_moves_lower_limit():
    mild = configure_for_environment(DEFAULT, ambient_c=28.0)
    assert mild.temperature_check_enabled is True
    assert mild.temp_min_c == 30.0 and mild.temp_max_c == 42.0
    assert classify_seat(2600, 31.0, mild) == OCCUPIED
    assert classify_seat(2600, 28.4, mild) == OBJECT
    assert DEFAULT.temp_min_c == 34.0


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        SeatConfig(temp_min_c=40, temp_max_c=35).validate()
    with pytest.raises(ValueError):
        SeatConfig(pressure_threshold=5000).validate()


def test_debounce_ignores_single_spike():
    d = SeatDebouncer(DEFAULT)
    assert d.update(OCCUPIED) == EMPTY
    assert d.update(EMPTY) == EMPTY
    assert d.update(OCCUPIED) == EMPTY
    assert d.update(OCCUPIED) == EMPTY
    assert d.update(OCCUPIED) == OCCUPIED


def test_free_seat_count_excludes_objects():
    assert free_seat_count([EMPTY, OBJECT, OCCUPIED, EMPTY]) == 2


def test_nmea_round_trip():
    s = build_nmea_rmc(28.6139, 77.2090, 8.0)
    fix = parse_nmea_rmc(s)
    assert abs(fix["lat"] - 28.6139) < 1e-5
    assert abs(fix["lon"] - 77.2090) < 1e-5
    assert abs(fix["speed_mps"] - 8.0) < 0.01


def test_nmea_bad_checksum():
    s = build_nmea_rmc(12.97, 79.15, 0.0)
    with pytest.raises(ValueError):
        parse_nmea_rmc(s[:-2] + "00")


def test_nmea_void_fix_returns_none():
    data = "GPRMC,120000.00,V,,,,,,,161026,,,N"
    c = 0
    for ch in data:
        c ^= ord(ch)
    assert parse_nmea_rmc(f"${data}*{c:02X}") is None


def test_haversine_known_distance():
    d = haversine_m(28.6139, 77.2090, 28.6139, 77.2190)
    assert 970 < d < 985


def test_stationary_rules():
    a = {"lat": 12.97, "lon": 79.15, "speed_mps": 0.1}
    b = {"lat": 12.97001, "lon": 79.15, "speed_mps": 0.2}
    c = {"lat": 12.9702, "lon": 79.15, "speed_mps": 3.0}
    assert is_stationary(a, b) is True
    assert is_stationary(a, c) is False
    assert is_stationary(None, b) is False


def test_gate():
    assert boarding_allowed(True, True)
    assert not boarding_allowed(True, False)
    assert not boarding_allowed(False, True)


def test_identity_modes():
    db = {"face-123": "INST-21001"}
    ok = verify_rider(IdentityMode.INSTITUTIONAL_FACE, "face-123", db.get)
    assert ok["ok"] and ok["rider_ref"] and "21001" not in ok["rider_ref"]
    bad = verify_rider(IdentityMode.INSTITUTIONAL_FACE, "face-999", db.get)
    assert not bad["ok"]
    pub = verify_rider(IdentityMode.PUBLIC_TICKET, "NCMC:6075xxxx1234", None)
    assert pub["ok"] and pub["medium"] == "NCMC"
    assert not verify_rider(IdentityMode.PUBLIC_TICKET, "CASH:1", None)["ok"]
    assert not verify_rider(IdentityMode.PUBLIC_TICKET, "QR:", None)["ok"]


DELHI_STYLE = slab_policy([(4, 5), (10, 10), (math.inf, 15)], name="three-slab")


@pytest.mark.parametrize("km,expected", [(0.5, 5), (4.0, 5), (4.01, 10), (10.0, 10), (10.01, 15), (25, 15)])
def test_slab_fares(km, expected):
    assert base_fare(DELHI_STYLE, km) == expected


def test_stage_fares():
    p = stage_policy(2.0, [6, 8, 10, 12, 14])
    assert base_fare(p, 0.3) == 6
    assert base_fare(p, 2.0) == 6
    assert base_fare(p, 2.01) == 8
    assert base_fare(p, 40) == 14


def test_per_km_and_flat():
    assert base_fare(per_km_policy(5.0, 2.0), 0.2) == 2.0
    assert base_fare(per_km_policy(5.0, 2.0), 3.0) == 15.0
    assert base_fare(flat_policy(20), 9.0) == 20


def test_fare_record_schema_is_identical_across_policies():
    keys = None
    for pol in (DELHI_STYLE, stage_policy(2.0, [6, 8, 10]), per_km_policy(), flat_policy(10)):
        rec = fare_record("T1", "abc", "NCMC", "S01", "S07", 5.2, pol)
        if keys is None:
            keys = set(rec)
        assert set(rec) == keys


def test_zero_fare_concession_still_recorded():
    rec = fare_record("T1", "abc", "PASS", "S01", "S07", 5.2, DELHI_STYLE, concession=0.0, concession_label="FREE_SCHEME")
    assert rec["amount"] == 0.0 and rec["base_amount"] == 10.0


def test_eta_estimator():
    e = EtaEstimator(alpha=1.0, dwell_s=20)
    e.observe(100, 10)
    assert e.eta_s(1000, 2) == pytest.approx(140.0)
    e.observe(0, 10)
    assert e.eta_s(150, 0) == pytest.approx(100.0)


def test_board_rows_sorted_and_flagged():
    arrivals = [
        {"route": "21A", "bus": "B2", "eta_s": 600, "free_seats": 0, "updated_s": 100},
        {"route": "21A", "bus": "B1", "eta_s": 120, "free_seats": 12, "updated_s": 190},
        {"route": "21A", "bus": "B3", "eta_s": 900, "free_seats": 4, "updated_s": 195},
    ]
    board = build_stop_board("S05", "Main Gate", arrivals, now_s=200)
    assert [r["bus"] for r in board["rows"]] == ["B1", "B2", "B3"]
    assert board["rows"][0]["label"] == "SEATS AVAILABLE"
    assert board["rows"][1]["label"] == "NO SEATS" and board["rows"][1]["approximate"]
    assert board["rows"][2]["label"] == "FEW SEATS"
    assert seat_label(5) == "FEW SEATS" and seat_label(6) == "SEATS AVAILABLE"


def test_payload_sizes():
    fix = {"lat": 28.613912, "lon": 77.209012, "speed_mps": 7.25}
    s = build_seat_summary("DL1PC1234", "21A", 42, fix, [EMPTY] * 30 + [OCCUPIED] * 14, False, 1760000000)
    assert len(encode(s).encode()) < 400
    assert len(build_sms_summary(s)) <= 160


from transit_core import assess_event


@pytest.mark.parametrize("ev,tier", [
    ({}, "T1"),
    ({"occupied_seats": 30, "validated_tickets": 28}, "T1"),
    ({"occupied_seats": 30, "validated_tickets": 20}, "T2"),
    ({"gps_jump": True}, "T2"),
    ({"silent_s": 180}, "T2"),
    ({"entry_exit_unpaired": True}, "T2"),
    ({"boarding_registered": True, "stationary_at_event": False}, "T3"),
    ({"door_open_while_moving": True, "gps_jump": True}, "T3"),
    ({"faulty_seats": 6}, "T3"),
    ({"rider_rejected_but_entered": True}, "T3"),
])
def test_escalation_tiers(ev, tier):
    assert assess_event(ev)["tier"] == tier


def test_escalation_recipients():
    assert assess_event({})["recipient"] == "LOG_ONLY"
    assert assess_event({"gps_jump": True})["recipient"] == "CONTROL_ROOM"
    assert assess_event({"faulty_seats": 9})["recipient"] == "CONTROL_ROOM_AND_MAINTENANCE"
