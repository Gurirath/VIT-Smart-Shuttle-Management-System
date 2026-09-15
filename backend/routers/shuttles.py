from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import ShuttleResponse, SeatResponse, GPSUpdate, NetworkUpdate
from typing import List
import math

router = APIRouter(prefix="/api/shuttles", tags=["shuttles"])

# Campus route stops for route progress calculation
ROUTE_STOPS = [
    {"name": "Main Gate", "lat": 12.9682, "lng": 79.1558},
    {"name": "Academic Block", "lat": 12.9700, "lng": 79.1575},
    {"name": "SJT", "lat": 12.9718, "lng": 79.1590},
    {"name": "Library", "lat": 12.9733, "lng": 79.1605},
    {"name": "Hostels", "lat": 12.9748, "lng": 79.1622},
]

def compute_route_progress(latitude: float, longitude: float) -> float:
    total_route_dist = math.sqrt(
        (ROUTE_STOPS[-1]["lat"] - ROUTE_STOPS[0]["lat"])**2 +
        (ROUTE_STOPS[-1]["lng"] - ROUTE_STOPS[0]["lng"])**2
    ) * 111
    current_dist = math.sqrt(
        (latitude - ROUTE_STOPS[0]["lat"])**2 +
        (longitude - ROUTE_STOPS[0]["lng"])**2
    ) * 111
    if total_route_dist <= 0:
        return 0.0
    return round(min(100.0, (current_dist / total_route_dist) * 100), 1)

def seat_to_response(seat: models.Seat) -> SeatResponse:
    return SeatResponse(
        id=str(seat.id),
        number=seat.seat_number,
        status=seat.status,
        studentId=seat.student_id,
        studentName=seat.student_name,
        gender=seat.gender,
        temperature=seat.temperature,
        pressure=seat.pressure,
        entryTime=seat.entry_time,
        tripId=seat.trip_id,
    )

def shuttle_to_response(shuttle: models.Shuttle, include_seats: bool = True) -> ShuttleResponse:
    seats = [seat_to_response(s) for s in sorted(shuttle.seats, key=lambda x: x.seat_number)] if include_seats else []
    return ShuttleResponse(
        id=shuttle.shuttle_id,
        name=shuttle.name,
        status=shuttle.status,
        passengers=shuttle.passenger_count,
        capacity=shuttle.capacity,
        latitude=shuttle.latitude,
        longitude=shuttle.longitude,
        routeProgress=shuttle.route_progress,
        network=shuttle.network_mode,
        currentTrip=shuttle.current_trip or "",
        distance=round(shuttle.distance, 2),
        estimatedFare=round(shuttle.estimated_fare, 2),
        currentRoute=shuttle.current_route,
        seats=seats,
    )

@router.get("", response_model=List[ShuttleResponse])
def get_shuttles(db: Session = Depends(get_db)):
    shuttles = db.query(models.Shuttle).all()
    return [shuttle_to_response(s, include_seats=True) for s in shuttles]

@router.get("/{shuttle_id}", response_model=ShuttleResponse)
def get_shuttle(shuttle_id: str, db: Session = Depends(get_db)):
    shuttle = db.query(models.Shuttle).filter(models.Shuttle.shuttle_id == shuttle_id).first()
    if not shuttle:
        raise HTTPException(status_code=404, detail="Shuttle not found")
    return shuttle_to_response(shuttle, include_seats=True)

@router.post("/{shuttle_id}/gps")
def update_gps(shuttle_id: str, data: GPSUpdate, db: Session = Depends(get_db)):
    shuttle = db.query(models.Shuttle).filter(models.Shuttle.shuttle_id == shuttle_id).first()
    if not shuttle:
        raise HTTPException(status_code=404, detail="Shuttle not found")
    
    # Calculate distance from previous position
    prev_lat, prev_lng = shuttle.latitude, shuttle.longitude
    d = math.sqrt((data.latitude - prev_lat)**2 + (data.longitude - prev_lng)**2) * 111  # approx km
    shuttle.distance = round(shuttle.distance + d, 3)
    shuttle.estimated_fare = round(max(2.0, shuttle.distance * 5.0), 2)
    
    shuttle.latitude = data.latitude
    shuttle.longitude = data.longitude

    # Calculate route progress (0-100) based on nearest stop
    shuttle.route_progress = compute_route_progress(data.latitude, data.longitude)
    
    # Log GPS update
    log_entry = models.VehicleLogEntry(
        shuttle_id=shuttle_id,
        shuttle_name=shuttle.name,
        timestamp=_now_str(),
        event="GPS_UPDATE",
        latitude=data.latitude,
        longitude=data.longitude,
        distance_km=round(shuttle.distance, 2),
        passengers=shuttle.passenger_count,
        network_mode=shuttle.network_mode,
    )
    db.add(log_entry)
    db.commit()
    return {"message": "GPS updated", "route_progress": shuttle.route_progress}

@router.post("/{shuttle_id}/network")
def update_network(shuttle_id: str, data: NetworkUpdate, db: Session = Depends(get_db)):
    shuttle = db.query(models.Shuttle).filter(models.Shuttle.shuttle_id == shuttle_id).first()
    if not shuttle:
        raise HTTPException(status_code=404, detail="Shuttle not found")
    
    old_mode = shuttle.network_mode
    shuttle.network_mode = data.network_mode
    
    event_name = {
        "WIFI_MQTT": "WIFI_RESTORED",
        "GSM_FALLBACK": "GSM_FALLBACK",
        "OFFLINE": "WIFI_LOST",
    }.get(data.network_mode, "NETWORK_CHANGE")
    
    log_entry = models.VehicleLogEntry(
        shuttle_id=shuttle_id,
        shuttle_name=shuttle.name,
        timestamp=_now_str(),
        event=event_name,
        latitude=shuttle.latitude,
        longitude=shuttle.longitude,
        distance_km=round(shuttle.distance, 2),
        passengers=shuttle.passenger_count,
        network_mode=data.network_mode,
    )
    db.add(log_entry)
    db.commit()
    return {"message": f"Network switched to {data.network_mode}"}

def _now_str():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%H:%M")
