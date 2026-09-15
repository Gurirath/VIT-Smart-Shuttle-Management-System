from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import VehicleLogResponse, VehicleEventResponse
from typing import List

router = APIRouter(prefix="/api/vehicle-logs", tags=["vehicle-logs"])

@router.get("", response_model=List[VehicleLogResponse])
def get_vehicle_logs(db: Session = Depends(get_db)):
    """Aggregate per-shuttle log summary + events."""
    shuttles = db.query(models.Shuttle).all()
    result = []
    for shuttle in shuttles:
        events = db.query(models.VehicleLogEntry).filter(
            models.VehicleLogEntry.shuttle_id == shuttle.shuttle_id
        ).order_by(models.VehicleLogEntry.id.desc()).limit(50).all()
        
        trips = db.query(models.Trip).filter(models.Trip.shuttle_id == shuttle.shuttle_id).all()
        total_trips = len(trips)
        total_dist = round(sum(t.distance_km for t in trips), 2)
        total_passengers = sum(1 for t in trips if t.exit_time is not None)
        avg_occ = round((shuttle.passenger_count / shuttle.capacity) * 100, 1) if shuttle.capacity > 0 else 0.0
        
        wifi_events = [e for e in events if e.network_mode == "WIFI_MQTT"]
        net_avail = round((len(wifi_events) / len(events)) * 100, 1) if events else 98.0
        
        fuel = round(total_dist * 0.12, 1)  # 0.12 L/km estimate
        
        event_responses = []
        for e in reversed(events):  # chronological
            event_responses.append(VehicleEventResponse(
                id=str(e.id),
                time=e.timestamp,
                event=e.event,
                location=f"{e.latitude:.4f},{e.longitude:.4f}" if e.latitude else "Campus",
                distance=e.distance_km,
                passengers=e.passengers,
                network=e.network_mode,
            ))
        
        result.append(VehicleLogResponse(
            id=shuttle.shuttle_id,
            shuttleId=shuttle.shuttle_id,
            shuttleName=shuttle.name,
            totalTrips=total_trips,
            totalDistance=total_dist,
            fuelConsumed=fuel,
            passengersServed=total_passengers,
            averageOccupancy=avg_occ,
            networkAvailability=net_avail,
            events=event_responses,
        ))
    return result
