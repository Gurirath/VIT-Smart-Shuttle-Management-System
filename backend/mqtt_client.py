import os
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from database import SessionLocal
import models
from schemas import TripEntryRequest, TripExitRequest
from routers.trips import trip_entry, trip_exit
from routers.shuttles import compute_route_progress

SEAT_STATE_TO_STATUS = {"EMPTY": "AVAILABLE", "OBJECT": "OBJECT", "STUDENT": "OCCUPIED"}
SEAT_PRESSURE_THRESHOLD = 1200  # matches PRESSURE_THRESHOLD in the ESP32 sketch

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

is_connected = False

def on_connect(client, userdata, flags, reason_code, properties=None):
    global is_connected
    if reason_code == 0:
        is_connected = True
        print(f"[MQTT] CONNECTED")
        client.subscribe("vit/shuttle1/#")
        print(f"[MQTT] SUBSCRIBED: vit/shuttle1/#")
    else:
        print(f"[MQTT] CONNECTION FAILED with result code {reason_code}")

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    global is_connected
    is_connected = False
    print(f'[MQTT] DISCONNECTED')

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    print(f"[MQTT RECEIVED]\nTopic: {msg.topic}\nPayload: {payload}")
    
    db = SessionLocal()
    try:
        if msg.topic == "vit/shuttle1/gps":
            process_gps(db, payload)
        elif msg.topic == "vit/shuttle1/seat":
            process_seat(db, payload)
        elif msg.topic == "vit/shuttle1/billing":
            process_billing(db, payload)
    except Exception as e:
        print(f"[MQTT ERROR] Failed to process {msg.topic}: {e}")
    finally:
        db.close()

def process_gps(db, payload):
    try:
        lat_str, lng_str = payload.split(',')
        lat, lng = float(lat_str), float(lng_str)
    except ValueError:
        return
    
    shuttle = db.query(models.Shuttle).filter(models.Shuttle.shuttle_id == "VIT-SHUTTLE-01").first()
    if not shuttle:
        return
        
    shuttle.latitude = lat
    shuttle.longitude = lng
    shuttle.route_progress = compute_route_progress(lat, lng)
    
    log = models.VehicleLogEntry(
        shuttle_id="VIT-SHUTTLE-01",
        shuttle_name=shuttle.name,
        timestamp=datetime.now(timezone.utc).strftime("%H:%M"),
        event="GPS_UPDATE",
        latitude=lat,
        longitude=lng,
        distance_km=shuttle.distance,
        passengers=shuttle.passenger_count,
        network_mode=shuttle.network_mode,
    )
    db.add(log)
    db.commit()
    print("[MQTT] GPS updated\nShuttle: VIT-SHUTTLE-01")

def process_seat(db, payload):
    # Sketch payload: "STATE,TEMP=36.7,PRESSURE=1250" where STATE is EMPTY/OBJECT/STUDENT
    # (the ESP32 already classifies the seat itself; we don't re-derive it here).
    parts = payload.split(',')
    if len(parts) != 3:
        print(f"[MQTT] Seat parser: malformed payload {payload!r} (expected 3 comma parts) - ignoring")
        return
    state_name = parts[0].strip().upper()
    new_status = SEAT_STATE_TO_STATUS.get(state_name)
    if new_status is None:
        # Reject unknown classifications loudly rather than silently dropping them.
        # (e.g. the pre-rename sketch value "BAG" now lands here and is ignored.)
        print(f"[MQTT] Seat parser: unexpected seat state {state_name!r} in payload {payload!r} - "
              f"expected one of {sorted(SEAT_STATE_TO_STATUS)} - ignoring")
        return
    try:
        temperature = float(parts[1].split('=', 1)[1])
        pressure_raw = int(parts[2].split('=', 1)[1])
    except (IndexError, ValueError):
        return

    seat = db.query(models.Seat).filter(
        models.Seat.shuttle_id == "VIT-SHUTTLE-01",
        models.Seat.seat_number == 1
    ).first()
    if not seat:
        return

    seat.pressure = "HIGH" if pressure_raw >= SEAT_PRESSURE_THRESHOLD else "LOW"
    seat.temperature = temperature

    if seat.trip_id is not None:
        # A boarding transaction already owns this seat - only the EXIT billing
        # event may end it and free the seat. Otherwise a momentary EMPTY/OBJECT
        # sensor blip (e.g. the pot wobbling) would silently wipe seat.status
        # to AVAILABLE while student_id/trip_id stay attached, corrupting state.
        db.commit()
        return

    if new_status == "OCCUPIED":
        # The sketch's seat sensor fires before the face-scan button (checkSeat()
        # runs before checkButton() every loop), so a sensor-only "STUDENT" reading
        # must not claim the seat itself - that would make the follow-up ENTRY
        # billing event get rejected as "seat already occupied" by trip_entry().
        # Leave status alone; trip_entry() is what legitimately claims the seat.
        db.commit()
        print("[MQTT] Seat 1 sensor: STUDENT detected, awaiting face scan")
        return

    seat.status = new_status
    db.commit()
    print(f"[MQTT] Seat 1 -> {new_status}")

def process_billing(db, payload):
    # Sketch payload: "ENTRY,VIT21001,<lat>,<lng>" or "EXIT,VIT21001,<dist>km,Rs<fare>"
    parts = payload.split(',')
    if not parts:
        return
    action = parts[0].strip().upper()
    if action == "ENTRY":
        process_entry(db, parts)
    elif action == "EXIT":
        process_exit(db, parts)

def process_entry(db, parts):
    if len(parts) < 4:
        return
    student_id = parts[1].strip()
    try:
        latitude, longitude = float(parts[2]), float(parts[3])
    except ValueError:
        return

    # The sketch generates sequential virtual IDs (VIT21001..VIT21030, one per
    # MAX_PASSENGERS slot) that go well past the 10 demo students seed.py
    # pre-creates. Auto-register any ID the live hardware sends but the DB
    # doesn't know yet - otherwise entry 404s silently, the seat never gets
    # claimed, and the sketch's own passengerCount permanently desyncs from
    # the backend's passenger_count.
    student = db.query(models.Student).filter(models.Student.register_number == student_id).first()
    if not student:
        student = models.Student(
            register_number=student_id,
            name=f"Student {student_id}",
            gender="Male",
            department="UNKNOWN",
            fee_account=f"FEE-{student_id}",
        )
        db.add(student)
        db.commit()
        print(f"[MQTT] Auto-registered new student {student_id}")

    # The sketch's own sequential IDs (VIT21001, 21002, ...) can collide with
    # demo/historical seed data for OTHER shuttles, or with a session that
    # never cleanly exited. A live ENTRY event is ground truth about where
    # this student physically is right now, so release any stale prior seat
    # instead of rejecting the real boarding - otherwise a chunk of every
    # rapid-click test silently fails with "already on shuttle X" while the
    # sketch's own passengerCount keeps counting them as boarded.
    if student.status == "ON_SHUTTLE" and student.current_shuttle and student.current_seat:
        print(f"[MQTT] {student_id} was already marked on {student.current_shuttle} - releasing stale seat for live re-entry")
        prior_shuttle = db.query(models.Shuttle).filter(models.Shuttle.shuttle_id == student.current_shuttle).first()
        try:
            trip_exit(TripExitRequest(
                student_id=student_id, shuttle_id=student.current_shuttle, seat_number=student.current_seat,
                latitude=prior_shuttle.latitude if prior_shuttle else 12.98,
                longitude=prior_shuttle.longitude if prior_shuttle else 79.17,
                distance_km=0.0, fare=2.0,
            ), db)
        except Exception as e:
            print(f"[MQTT] Failed to release stale seat for {student_id}: {e}")

    # The sketch only has one physical seat sensor, but the shuttle has 30 logical
    # seats - board each new passenger into the next free one instead of always
    # fighting over "seat 1", so repeated face-scans actually fill up the shuttle.
    seat = db.query(models.Seat).filter(
        models.Seat.shuttle_id == "VIT-SHUTTLE-01",
        models.Seat.status == "AVAILABLE"
    ).order_by(models.Seat.seat_number).first()
    if not seat:
        print(f"[MQTT] Entry error: shuttle full, no available seat for {student_id}")
        return

    req = TripEntryRequest(student_id=student_id, shuttle_id="VIT-SHUTTLE-01", seat_number=seat.seat_number, latitude=latitude, longitude=longitude)
    try:
        trip_entry(req, db)
        print(f"[MQTT] Entry recorded for {student_id} (seat {seat.seat_number})")
    except Exception as e:
        print(f"[MQTT] Entry error: {e}")

def process_exit(db, parts):
    if len(parts) < 2:
        return
    student_id = parts[1].strip()

    # Find whichever seat this student actually boarded into (see process_entry).
    seat = db.query(models.Seat).filter(
        models.Seat.shuttle_id == "VIT-SHUTTLE-01",
        models.Seat.student_id == student_id
    ).first()
    if not seat:
        print(f"[MQTT] Exit error: {student_id} has no active seat on VIT-SHUTTLE-01")
        return

    # The sketch's EXIT message carries its own distance/fare (it tracks this
    # passenger's individual entry/exit GPS) - use those directly instead of
    # re-deriving a number from the shuttle's current position, which is wrong
    # for anyone but the passenger who happens to be exiting exactly now.
    distance_km = fare = None
    if len(parts) >= 4:
        try:
            distance_km = float(parts[2].strip().rstrip("km"))
            fare = float(parts[3].strip().lstrip("Rs"))
        except ValueError:
            distance_km = fare = None

    shuttle = db.query(models.Shuttle).filter(models.Shuttle.shuttle_id == "VIT-SHUTTLE-01").first()
    latitude = shuttle.latitude if shuttle else 12.98
    longitude = shuttle.longitude if shuttle else 79.17

    req = TripExitRequest(
        student_id=student_id, shuttle_id="VIT-SHUTTLE-01", seat_number=seat.seat_number,
        latitude=latitude, longitude=longitude, distance_km=distance_km, fare=fare,
    )
    try:
        trip_exit(req, db)
        print(f"[MQTT] Exit recorded for {student_id} (seat {seat.seat_number})")
    except Exception as e:
        print(f"[MQTT] Exit error: {e}")

def start_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT}")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"[MQTT] CONNECTION FAILED: {e}")
