import sys
import os

# Add current directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import models

def now_str():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M")

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 1. Idempotency check
    if db.query(models.Shuttle).count() > 0:
        print("Database already seeded. Skipping.")
        db.close()
        return

    print("Starting database seed...")
    
    # 2. Create Students
    students_data = [
        {"reg": "VIT21001", "name": "Rahul Sharma", "gender": "Male", "dept": "CSE", "status": "ON_SHUTTLE", "shuttle": "VIT-SHUTTLE-02", "seat": 1},
        {"reg": "VIT21002", "name": "Priya Nair", "gender": "Female", "dept": "ECE", "status": "ON_CAMPUS", "shuttle": None, "seat": None},
        {"reg": "VIT21003", "name": "Arjun Reddy", "gender": "Male", "dept": "MECH", "status": "ON_SHUTTLE", "shuttle": "VIT-SHUTTLE-02", "seat": 2},
        {"reg": "VIT21004", "name": "Ananya Krishnan", "gender": "Female", "dept": "IT", "status": "ON_CAMPUS", "shuttle": None, "seat": None},
        {"reg": "VIT21005", "name": "Karthik Subramaniam", "gender": "Male", "dept": "BIO", "status": "ON_SHUTTLE", "shuttle": "VIT-SHUTTLE-02", "seat": 3},
        {"reg": "VIT21006", "name": "Meera Pillai", "gender": "Female", "dept": "CSE", "status": "ON_CAMPUS", "shuttle": None, "seat": None},
        {"reg": "VIT21007", "name": "Vikram Singh", "gender": "Male", "dept": "ECE", "status": "ON_CAMPUS", "shuttle": None, "seat": None},
        {"reg": "VIT21008", "name": "Deepa Menon", "gender": "Female", "dept": "MECH", "status": "ON_CAMPUS", "shuttle": None, "seat": None},
        {"reg": "VIT21009", "name": "Sanjay Kumar", "gender": "Male", "dept": "IT", "status": "OFF_CAMPUS", "shuttle": None, "seat": None},
        {"reg": "VIT21010", "name": "Lakshmi Patel", "gender": "Female", "dept": "BIO", "status": "ON_CAMPUS", "shuttle": None, "seat": None},
    ]

    for sd in students_data:
        student = models.Student(
            register_number=sd["reg"],
            name=sd["name"],
            gender=sd["gender"],
            department=sd["dept"],
            fee_account=f"FEE-{sd['reg']}",
            payment_status="ACTIVE",
            status=sd["status"],
            current_shuttle=sd["shuttle"],
            current_seat=sd["seat"],
        )
        db.add(student)
    db.commit()

    # 3. Create Shuttles
    s1 = models.Shuttle(
        shuttle_id="VIT-SHUTTLE-01", name="VIT-SHUTTLE-01", capacity=30, status="RUNNING",
        latitude=12.969574, longitude=79.155987, route_progress=0.0, network_mode="WIFI_MQTT",
        passenger_count=0, distance=0.0, estimated_fare=0.0
    )
    s2 = models.Shuttle(
        shuttle_id="VIT-SHUTTLE-02", name="VIT-SHUTTLE-02", capacity=30, status="RUNNING",
        latitude=12.972000, longitude=79.160000, route_progress=80.0, network_mode="GSM_FALLBACK",
        passenger_count=3, distance=8.2, estimated_fare=41.0
    )
    db.add_all([s1, s2])
    db.commit()
    db.refresh(s1)
    db.refresh(s2)

    # 4. Create Seats
    # Shuttle 1 Seats - this shuttle is driven by the live ESP32/Wokwi sketch,
    # so it boots with all 30 seats empty; real occupancy comes from MQTT
    # seat sensor + billing ENTRY events, not baked-in demo data.
    shuttle1_seats = {}
    
    for i in range(1, 31):
        info = shuttle1_seats.get(i, {"status": "AVAILABLE", "student": None, "temp": None, "pressure": "LOW" if not shuttle1_seats.get(i) else "HIGH"})
        student_obj = db.query(models.Student).filter(models.Student.register_number == info["student"]).first() if info["student"] else None
        
        seat = models.Seat(
            shuttle_db_id=s1.id, shuttle_id=s1.shuttle_id, seat_number=i,
            status=info["status"],
            student_id=info["student"],
            student_name=student_obj.name if student_obj else None,
            gender=student_obj.gender if student_obj else None,
            temperature=info["temp"],
            pressure=info["pressure"],
            entry_time=now_str() if info["status"] == "OCCUPIED" else None
        )
        db.add(seat)
        
    # Shuttle 2 Seats
    shuttle2_seats = {
        1: {"status": "OCCUPIED", "student": "VIT21001", "temp": 36.2, "pressure": "HIGH"},
        2: {"status": "OCCUPIED", "student": "VIT21003", "temp": 36.8, "pressure": "HIGH"},
        3: {"status": "OCCUPIED", "student": "VIT21005", "temp": 37.1, "pressure": "HIGH"},
    }
    
    for i in range(1, 31):
        info = shuttle2_seats.get(i, {"status": "AVAILABLE", "student": None, "temp": None, "pressure": "LOW" if not shuttle2_seats.get(i) else "HIGH"})
        student_obj = db.query(models.Student).filter(models.Student.register_number == info["student"]).first() if info["student"] else None
        
        seat = models.Seat(
            shuttle_db_id=s2.id, shuttle_id=s2.shuttle_id, seat_number=i,
            status=info["status"],
            student_id=info["student"],
            student_name=student_obj.name if student_obj else None,
            gender=student_obj.gender if student_obj else None,
            temperature=info["temp"],
            pressure=info["pressure"],
            entry_time=now_str() if info["status"] == "OCCUPIED" else None
        )
        db.add(seat)
    db.commit()

    # 5. Create Trips
    historical_trips = [
        {"id": "TRIP-001", "reg": "VIT21007", "shuttle": "VIT-SHUTTLE-01", "entry": "08:15", "exit": "08:45", "dist": 3.2, "fare": 16.00},
        {"id": "TRIP-002", "reg": "VIT21009", "shuttle": "VIT-SHUTTLE-01", "entry": "09:30", "exit": "09:55", "dist": 2.1, "fare": 10.50},
        {"id": "TRIP-003", "reg": "VIT21001", "shuttle": "VIT-SHUTTLE-02", "entry": "10:00", "exit": "10:20", "dist": 1.5, "fare": 7.50},
        {"id": "TRIP-004", "reg": "VIT21007", "shuttle": "VIT-SHUTTLE-01", "entry": "11:00", "exit": "11:30", "dist": 2.8, "fare": 14.00},
        {"id": "TRIP-005", "reg": "VIT21009", "shuttle": "VIT-SHUTTLE-02", "entry": "12:15", "exit": "12:40", "dist": 1.8, "fare": 9.00},
    ]
    for ht in historical_trips:
        student = db.query(models.Student).filter(models.Student.register_number == ht["reg"]).first()
        trip = models.Trip(
            trip_id=ht["id"], student_id=ht["reg"], student_name=student.name,
            shuttle_id=ht["shuttle"], shuttle_name=ht["shuttle"],
            entry_time=ht["entry"], exit_time=ht["exit"],
            entry_location="Main Gate", exit_location="Library",
            entry_lat=12.9682, entry_lng=79.1558, exit_lat=12.9733, exit_lng=79.1605,
            distance_km=ht["dist"], fare=ht["fare"], payment_status="PROCESSED",
        )
        db.add(trip)
    db.commit()
    
    # Add active trips - VIT-SHUTTLE-01 is intentionally excluded here (see
    # shuttle1_seats above): it boots empty since it's driven by live MQTT.
    active_students = [
        ("VIT21001", "VIT-SHUTTLE-02", 1, "TRIP-006"), ("VIT21003", "VIT-SHUTTLE-02", 2, "TRIP-007"),
        ("VIT21005", "VIT-SHUTTLE-02", 3, "TRIP-008")
    ]
    
    for reg, shut_id, seat_num, trip_id in active_students:
        student = db.query(models.Student).filter(models.Student.register_number == reg).first()
        trip = models.Trip(
            trip_id=trip_id, student_id=reg, student_name=student.name,
            shuttle_id=shut_id, shuttle_name=shut_id,
            entry_time=now_str(), entry_location="Main Gate",
            entry_lat=12.9682, entry_lng=79.1558, distance_km=0.0, fare=0.0, payment_status="PENDING",
        )
        db.add(trip)
        student.trip_id = trip_id
        
        seat = db.query(models.Seat).filter(models.Seat.shuttle_id == shut_id, models.Seat.seat_number == seat_num).first()
        seat.trip_id = trip_id
    db.commit()

    # 6. Create Vehicle Logs
    logs = []
    for s_id in ["VIT-SHUTTLE-01", "VIT-SHUTTLE-02"]:
        events = ["SHUTTLE_STARTED", "GPS_UPDATE", "PASSENGER_ENTRY", "WIFI_LOST", "GSM_FALLBACK", "GPS_UPDATE", "WIFI_RESTORED", "PASSENGER_EXIT", "GPS_UPDATE", "TRIP_COMPLETED"]
        for i, ev in enumerate(events):
            logs.append(models.VehicleLogEntry(
                shuttle_id=s_id, shuttle_name=s_id, timestamp=now_str(), event=ev,
                latitude=12.968 + i*0.001, longitude=79.155 + i*0.001,
                distance_km=i*0.5, passengers=i%30, network_mode="WIFI_MQTT" if "WIFI" in ev or "GPS" in ev else "GSM_FALLBACK"
            ))
    db.add_all(logs)
    db.commit()

    # 7. Create Shuttle Requests
    reqs = [
        {"id": "REQ-001", "reg": "VIT21007", "pickup": "Main Gate", "dest": "Hostels", "time": "14:00", "status": "PENDING"},
        {"id": "REQ-002", "reg": "VIT21009", "pickup": "SJT", "dest": "Library", "time": "13:30", "status": "ASSIGNED"},
        {"id": "REQ-003", "reg": "VIT21007", "pickup": "Library", "dest": "Main Gate", "time": "16:00", "status": "PENDING"},
        {"id": "REQ-004", "reg": "VIT21009", "pickup": "Academic Block", "dest": "SJT", "time": "15:30", "status": "PENDING"},
        {"id": "REQ-005", "reg": "VIT21007", "pickup": "Main Gate", "dest": "Academic Block", "time": "17:00", "status": "COMPLETED"},
    ]
    for r in reqs:
        student = db.query(models.Student).filter(models.Student.register_number == r["reg"]).first()
        sr = models.ShuttleRequest(
            request_id=r["id"], student_id=r["reg"], student_name=student.name,
            pickup_stop=r["pickup"], destination_stop=r["dest"], class_end_time=r["time"], status=r["status"]
        )
        db.add(sr)
    db.commit()

    print("Database seed completed successfully.")
    db.close()

if __name__ == "__main__":
    seed()
