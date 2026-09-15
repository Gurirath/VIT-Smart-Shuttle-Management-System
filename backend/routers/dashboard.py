from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Shuttle, Seat, ShuttleRequest, Trip
from schemas import DashboardStats, ActivityEntry
import models
from datetime import datetime, date, timezone
from typing import List

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    shuttles = db.query(Shuttle).all()
    active_shuttles = sum(1 for s in shuttles if s.status == "RUNNING")
    
    # Count occupied seats across ALL shuttles for consistency
    all_seats = db.query(Seat).all()
    passengers_on_board = sum(1 for seat in all_seats if seat.status == "OCCUPIED")
    total_capacity = sum(s.capacity for s in shuttles)
    available_seats = total_capacity - passengers_on_board
    
    pending_requests = db.query(ShuttleRequest).filter(
        ShuttleRequest.status.in_(["PENDING", "ASSIGNED"])
    ).count()
    
    # Today's trips
    today = date.today().isoformat()
    all_trips = db.query(Trip).all()
    todays_trips = [t for t in all_trips if t.entry_time and t.entry_time[:10] == today]
    if not todays_trips:
        # If no trips today, show total trips for demo
        todays_trips = all_trips
    todays_trip_count = len(todays_trips)
    todays_revenue = sum(t.fare for t in todays_trips if t.payment_status == "PROCESSED")
    
    return DashboardStats(
        activeShuttles=active_shuttles,
        passengersOnBoard=passengers_on_board,
        availableSeats=available_seats,
        shuttleRequests=pending_requests,
        todaysTrips=todays_trip_count,
        todaysRevenue=round(todays_revenue, 2),
    )

@router.get("/activities", response_model=List[ActivityEntry])
def get_activities(db: Session = Depends(get_db)):
    """Return recent vehicle log events as activity entries."""
    entries = db.query(models.VehicleLogEntry).order_by(
        models.VehicleLogEntry.id.desc()
    ).limit(20).all()
    
    result = []
    for e in entries:
        event_lower = e.event.lower()
        if "passenger_entry" in event_lower:
            etype = "entry"
        elif "passenger_exit" in event_lower:
            etype = "exit"
        elif "wifi" in event_lower or "gsm" in event_lower or "network" in event_lower or "offline" in event_lower:
            etype = "network"
        elif "bag" in event_lower or "object" in event_lower:
            etype = "detection"
        else:
            etype = "system"
        result.append(ActivityEntry(
            id=str(e.id),
            message=f"{e.shuttle_id}: {e.event}",
            timestamp=e.timestamp,
            type=etype,
        ))
    return result
