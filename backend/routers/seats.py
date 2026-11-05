from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import SeatResponse, SensorRequest, SensorResponse
from typing import List, Optional
from datetime import datetime, timezone

router = APIRouter(tags=["seats"])

FALLBACK_BAND = (34.0, 42.0)
EPS_THERMAL = 1.5
CONTACT_RANGE = (29.0, 38.5)
CONTACT_TOL = 2.0
SKIN_PULL = 0.15
BLIND_MARGIN = 1.2


def expected_contact(cabin: float) -> float:
    return 35.0 + SKIN_PULL * (cabin - 35.0)


def classify_seat(pressure: str, temperature: float, cabin: Optional[float] = None) -> str:
    if pressure == "LOW":
        return "AVAILABLE"
    if cabin is None:
        return "OCCUPIED" if FALLBACK_BAND[0] <= temperature <= FALLBACK_BAND[1] else "OBJECT"
    if not CONTACT_RANGE[0] <= temperature <= CONTACT_RANGE[1]:
        return "OBJECT"
    tc = expected_contact(cabin)
    delta = abs(temperature - cabin)
    if delta >= EPS_THERMAL:
        return "OCCUPIED" if abs(temperature - tc) <= CONTACT_TOL else "OBJECT"
    half = EPS_THERMAL / (1 - SKIN_PULL) + BLIND_MARGIN
    return "OCCUPIED" if abs(cabin - tc) <= half else "OBJECT"

def seat_to_response(seat: models.Seat) -> SeatResponse:
    status = seat.status
    return SeatResponse(
        id=str(seat.id),
        number=seat.seat_number,
        status=status,
        studentId=seat.student_id,
        studentName=seat.student_name,
        gender=seat.gender,
        temperature=seat.temperature,
        pressure=seat.pressure,
        entryTime=seat.entry_time,
        tripId=seat.trip_id,
    )

@router.get("/api/shuttles/{shuttle_id}/seats", response_model=List[SeatResponse])
def get_seats(shuttle_id: str, db: Session = Depends(get_db)):
    shuttle = db.query(models.Shuttle).filter(models.Shuttle.shuttle_id == shuttle_id).first()
    if not shuttle:
        raise HTTPException(status_code=404, detail="Shuttle not found")
    seats = sorted(shuttle.seats, key=lambda x: x.seat_number)
    return [seat_to_response(s) for s in seats]

@router.get("/api/shuttles/{shuttle_id}/seats/{seat_number}", response_model=SeatResponse)
def get_single_seat(shuttle_id: str, seat_number: int, db: Session = Depends(get_db)):
    seat = db.query(models.Seat).filter(
        models.Seat.shuttle_id == shuttle_id,
        models.Seat.seat_number == seat_number,
    ).first()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    return seat_to_response(seat)

@router.post("/api/shuttles/{shuttle_id}/seats/{seat_number}/sensor", response_model=SensorResponse)
def update_sensor(shuttle_id: str, seat_number: int, data: SensorRequest, db: Session = Depends(get_db)):
    seat = db.query(models.Seat).filter(
        models.Seat.shuttle_id == shuttle_id,
        models.Seat.seat_number == seat_number,
    ).first()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    
    new_status = classify_seat(data.pressure, data.temperature, data.cabin_temperature)
    seat.status = new_status
    seat.temperature = data.temperature
    seat.pressure = data.pressure
    
    if new_status == "AVAILABLE":
        seat.student_id = None
        seat.student_name = None
        seat.gender = None
        seat.entry_time = None
        seat.trip_id = None
    
    # Update passenger count on shuttle
    shuttle = db.query(models.Shuttle).filter(models.Shuttle.shuttle_id == shuttle_id).first()
    if shuttle:
        occupied = db.query(models.Seat).filter(
            models.Seat.shuttle_id == shuttle_id,
            models.Seat.status == "OCCUPIED"
        ).count()
        shuttle.passenger_count = occupied
    
    # Log sensor event
    log = models.VehicleLogEntry(
        shuttle_id=shuttle_id,
        shuttle_name=shuttle.name if shuttle else shuttle_id,
        timestamp=datetime.now(timezone.utc).strftime("%H:%M"),
        event=f"Seat {seat_number}: {new_status} (T={data.temperature}°C, P={data.pressure})",
        latitude=shuttle.latitude if shuttle else 0.0,
        longitude=shuttle.longitude if shuttle else 0.0,
        distance_km=shuttle.distance if shuttle else 0.0,
        passengers=shuttle.passenger_count if shuttle else 0,
        network_mode=shuttle.network_mode if shuttle else "WIFI_MQTT",
    )
    db.add(log)
    db.commit()
    
    return SensorResponse(
        seat_number=seat_number,
        pressure=data.pressure,
        temperature=data.temperature,
        status=new_status,
        student_id=seat.student_id,
        gender=seat.gender,
    )
