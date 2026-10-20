import math
import time

PRESSURE_THRESHOLD = 1200
HUMAN_TEMP_MIN = 34.0
HUMAN_TEMP_MAX = 42.0
GPS_CHANGE_STEP = 5
STATIONARY_EPSILON = 15
LONG_PRESS_TIME_MS = 1500
FARE_PER_KM = 5.0
MINIMUM_FARE = 2.0
MAX_PASSENGERS = 30

START_LAT, START_LNG = 12.9692, 79.1559
END_LAT, END_LNG = 12.9725, 79.1630


def classify_seat(pressure, temperature):
    if pressure < PRESSURE_THRESHOLD:
        return "EMPTY"
    if HUMAN_TEMP_MIN <= temperature <= HUMAN_TEMP_MAX:
        return "STUDENT"
    return "OBJECT"


def is_stationary(prev_gps_raw, cur_gps_raw):
    return abs(cur_gps_raw - prev_gps_raw) < STATIONARY_EPSILON


def gps_to_latlng(raw_adc):
    ratio = raw_adc / 4095.0
    lat = START_LAT + ratio * (END_LAT - START_LAT)
    lng = START_LNG + ratio * (END_LNG - START_LNG)
    return lat, lng


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_fare(distance_km):
    return max(MINIMUM_FARE, distance_km * FARE_PER_KM)


def build_seat_payload(state, temperature, pressure):
    return f"{state},TEMP={temperature:.1f},PRESSURE={pressure}"


def build_billing_entry_payload(student_id, lat, lng):
    return f"ENTRY,VIT{student_id},{lat:.6f},{lng:.6f}"


def build_billing_exit_payload(student_id, distance_km, fare):
    return f"EXIT,VIT{student_id},{distance_km:.2f}km,Rs{fare:.2f}"


def scan_allowed(stationary, door_open):
    return stationary and door_open
