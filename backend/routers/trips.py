from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import TripEntryRequest, TripExitRequest, TripResponse
from typing import List, Optional
from datetime import datetime, timezone
import math

router = APIRouter(prefix="/api/trips", tags=["trips"])

def _now_str():
    return datetime.now(timezone.utc).strftime("%H:%M")

def _distance(lat1, lng1, lat2, lng2):
    """Approx km between two lat/lng points."""
    return round(math.sqrt((lat2 - lat1)**2 + (lng2 - lng1)**2) * 111, 2)

def trip_to_response(t: models.Trip) -> TripResponse:
    return TripResponse(
        id=t.trip_id,
        studentId=t.student_id,
        studentName=t.student_name,
        shuttleId=t.shuttle_id,
        shuttleName=t.shuttle_name,
        entryTime=t.entry_time,
        exitTime=t.exit_time,
        entryLocation=t.entry_location,
        exitLocation=t.exit_location,
        entryGps={"lat": t.entry_lat, "lng": t.entry_lng},
        exitGps={"lat": t.exit_lat, "lng": t.exit_lng} if t.exit_lat is not None else None,
        distance=round(t.distance_km, 2),
        fare=round(t.fare, 2),
        paymentStatus=t.payment_status,
    )

@router.get("", response_model=List[TripResponse])
def get_trips(db: Session = Depends(get_db)):
    trips = db.query(models.Trip).order_by(models.Trip.id.desc()).all()
    return [trip_to_response(t) for t in trips]

@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: str, db: Session = Depends(get_db)):
    t = db.query(models.Trip).filter(models.Trip.trip_id == trip_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip_to_response(t)

@router.post("/entry", response_model=TripResponse)
def trip_entry(data: TripEntryRequest, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(
        models.Student.register_number == data.student_id
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if student.status == "ON_SHUTTLE":
        raise HTTPException(status_code=400, detail=f"Student {data.student_id} is already on shuttle {student.current_shuttle}")

    shuttle = db.query(models.Shuttle).filter(
        models.Shuttle.shuttle_id == data.shuttle_id
    ).first()
    if not shuttle:
        raise HTTPException(status_code=404, detail="Shuttle not found")
    
    seat = db.query(models.Seat).filter(
        models.Seat.shuttle_id == data.shuttle_id,
        models.Seat.seat_number == data.seat_number,
    ).first()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    if seat.status == "OCCUPIED":
        raise HTTPException(status_code=400, detail="Seat already occupied")
    
    # Generate trip ID from the highest existing numeric suffix, not row COUNT(*) -
    # count() drifts out of sync with real IDs whenever any trip row is deleted,
    # causing a UNIQUE constraint collision on the next entry.
    max_num = 0
    for (tid,) in db.query(models.Trip.trip_id).all():
        try:
            max_num = max(max_num, int(tid.split("-")[1]))
        except (IndexError, ValueError):
            pass
    trip_id = f"TRIP-{str(max_num + 1).zfill(3)}"
    now = _now_str()
    
    # Create trip
    trip = models.Trip(
        trip_id=trip_id,
        student_id=data.student_id,
        student_name=student.name,
        shuttle_id=data.shuttle_id,
        shuttle_name=shuttle.name,
        entry_time=now,
        exit_time=None,
        entry_location="Main Gate",
        exit_location=None,
        entry_lat=data.latitude,
        entry_lng=data.longitude,
        exit_lat=None,
        exit_lng=None,
        distance_km=0.0,
        fare=0.0,
        payment_status="PENDING",
    )
    db.add(trip)
    
    # Update seat
    seat.status = "OCCUPIED"
    seat.student_id = data.student_id
    seat.student_name = student.name
    seat.gender = student.gender
    seat.temperature = round(36.1 + (0 if student.gender == "Male" else 0.3), 1)
    seat.pressure = "HIGH"
    seat.entry_time = now
    seat.trip_id = trip_id
    
    # Update shuttle passenger count
    shuttle.passenger_count += 1
    shuttle.current_trip = trip_id
    
    # Update student
    student.status = "ON_SHUTTLE"
    student.current_shuttle = data.shuttle_id
    student.current_seat = data.seat_number
    student.trip_id = trip_id
    
    # Log
    log = models.VehicleLogEntry(
        shuttle_id=data.shuttle_id,
        shuttle_name=shuttle.name,
        timestamp=now,
        event=f"{data.student_id} PASSENGER_ENTRY (Seat {data.seat_number})",
        latitude=data.latitude,
        longitude=data.longitude,
        distance_km=shuttle.distance,
        passengers=shuttle.passenger_count,
        network_mode=shuttle.network_mode,
    )
    db.add(log)
    db.commit()
    db.refresh(trip)
    return trip_to_response(trip)

@router.post("/exit", response_model=TripResponse)
def trip_exit(data: TripExitRequest, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(
        models.Student.register_number == data.student_id
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    seat = db.query(models.Seat).filter(
        models.Seat.shuttle_id == data.shuttle_id,
        models.Seat.seat_number == data.seat_number,
    ).first()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    
    # Find the active trip
    trip = None
    if seat.trip_id:
        trip = db.query(models.Trip).filter(models.Trip.trip_id == seat.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="No active trip for this seat")
    
    shuttle = db.query(models.Shuttle).filter(
        models.Shuttle.shuttle_id == data.shuttle_id
    ).first()
    
    now = _now_str()
    if data.distance_km is not None:
        # Caller (e.g. the ESP32 sketch, which tracks this passenger's own
        # entry/exit GPS) already computed the real distance - trust it
        # instead of re-deriving a rough figure from the shuttle's current
        # position, which is wrong as soon as other passengers exit later.
        dist = data.distance_km
        fare = data.fare if data.fare is not None else round(max(2.0, dist * 5.0), 2)
    else:
        dist = _distance(trip.entry_lat, trip.entry_lng, data.latitude, data.longitude)
        if dist < 0.1:
            dist = round(0.5 + abs(hash(trip.trip_id)) % 20 / 10, 2)  # min realistic distance
        fare = round(max(2.0, dist * 5.0), 2)
    
    # Update trip
    trip.exit_time = now
    trip.exit_location = "Academic Block"
    trip.exit_lat = data.latitude
    trip.exit_lng = data.longitude
    trip.distance_km = dist
    trip.fare = fare
    trip.payment_status = "PROCESSED"
    
    # Free seat
    seat.status = "AVAILABLE"
    seat.student_id = None
    seat.student_name = None
    seat.gender = None
    seat.temperature = None
    seat.pressure = None
    seat.entry_time = None
    seat.trip_id = None
    
    # Update shuttle
    if shuttle:
        if shuttle.passenger_count > 0:
            shuttle.passenger_count -= 1
    
    # Update student
    student.status = "ON_CAMPUS"
    student.current_shuttle = None
    student.current_seat = None
    student.trip_id = None
    student.trips_today += 1
    student.total_distance = round(student.total_distance + dist, 2)
    student.total_fare = round(student.total_fare + fare, 2)
    student.active_payment_status = "PROCESSED"
    
    # Log
    if shuttle:
        log = models.VehicleLogEntry(
            shuttle_id=data.shuttle_id,
            shuttle_name=shuttle.name,
            timestamp=now,
            event=f"{data.student_id} PASSENGER_EXIT (Seat {data.seat_number}, Fare ₹{fare})",
            latitude=data.latitude,
            longitude=data.longitude,
            distance_km=round(shuttle.distance, 2),
            passengers=shuttle.passenger_count,
            network_mode=shuttle.network_mode,
        )
        db.add(log)
    
    db.commit()
    db.refresh(trip)
    return trip_to_response(trip)
