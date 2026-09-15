from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    register_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    gender = Column(String, nullable=False)  # Male / Female
    department = Column(String, nullable=False)
    fee_account = Column(String, nullable=False)
    payment_status = Column(String, default="ACTIVE")  # ACTIVE / SUSPENDED
    # runtime fields (updated per session)
    status = Column(String, default="ON_CAMPUS")  # ON_SHUTTLE / ON_CAMPUS / OFF_CAMPUS
    current_shuttle = Column(String, nullable=True)
    current_seat = Column(Integer, nullable=True)
    trips_today = Column(Integer, default=0)
    total_distance = Column(Float, default=0.0)
    total_fare = Column(Float, default=0.0)
    active_payment_status = Column(String, default="PROCESSED")  # PROCESSED / PENDING / FAILED
    trip_id = Column(String, nullable=True)

class Shuttle(Base):
    __tablename__ = "shuttles"
    id = Column(Integer, primary_key=True, index=True)
    shuttle_id = Column(String, unique=True, index=True, nullable=False)  # e.g. VIT-SHUTTLE-01
    name = Column(String, nullable=False)  # same as shuttle_id for display
    capacity = Column(Integer, default=30)
    status = Column(String, default="RUNNING")  # RUNNING / IDLE / MAINTENANCE
    latitude = Column(Float, default=12.969574)
    longitude = Column(Float, default=79.155987)
    route_progress = Column(Float, default=0.0)
    network_mode = Column(String, default="WIFI_MQTT")  # WIFI_MQTT / GSM_FALLBACK / OFFLINE
    current_trip = Column(String, default="")
    distance = Column(Float, default=0.0)
    estimated_fare = Column(Float, default=0.0)
    current_route = Column(String, default="Main Gate → Academic Block → SJT → Library → Hostels")
    passenger_count = Column(Integer, default=0)
    seats = relationship("Seat", back_populates="shuttle", cascade="all, delete-orphan")

class Seat(Base):
    __tablename__ = "seats"
    id = Column(Integer, primary_key=True, index=True)
    shuttle_db_id = Column(Integer, ForeignKey("shuttles.id"), nullable=False)
    shuttle_id = Column(String, nullable=False)  # VIT-SHUTTLE-01
    seat_number = Column(Integer, nullable=False)
    status = Column(String, default="AVAILABLE")  # AVAILABLE / OCCUPIED / OBJECT
    student_id = Column(String, nullable=True)
    student_name = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    temperature = Column(Float, nullable=True)
    pressure = Column(String, nullable=True)  # HIGH / LOW
    entry_time = Column(String, nullable=True)
    trip_id = Column(String, nullable=True)
    shuttle = relationship("Shuttle", back_populates="seats")

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(String, unique=True, index=True, nullable=False)  # TRIP-001
    student_id = Column(String, nullable=False)
    student_name = Column(String, nullable=False)
    shuttle_id = Column(String, nullable=False)  # VIT-SHUTTLE-01
    shuttle_name = Column(String, nullable=False)
    entry_time = Column(String, nullable=False)
    exit_time = Column(String, nullable=True)
    entry_location = Column(String, default="Main Gate")
    exit_location = Column(String, nullable=True)
    entry_lat = Column(Float, nullable=False)
    entry_lng = Column(Float, nullable=False)
    exit_lat = Column(Float, nullable=True)
    exit_lng = Column(Float, nullable=True)
    distance_km = Column(Float, default=0.0)
    fare = Column(Float, default=0.0)
    payment_status = Column(String, default="PENDING")  # PENDING / PROCESSED / FAILED
    created_at = Column(DateTime, default=utcnow)

class ShuttleRequest(Base):
    __tablename__ = "shuttle_requests"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, unique=True, index=True)
    student_id = Column(String, nullable=False)
    student_name = Column(String, nullable=False)
    pickup_stop = Column(String, nullable=False)
    destination_stop = Column(String, nullable=False)
    class_end_time = Column(String, nullable=False)
    status = Column(String, default="PENDING")  # PENDING / ASSIGNED / COMPLETED
    created_at = Column(DateTime, default=utcnow)

class VehicleLogEntry(Base):
    __tablename__ = "vehicle_log_entries"
    id = Column(Integer, primary_key=True, index=True)
    shuttle_id = Column(String, nullable=False, index=True)  # VIT-SHUTTLE-01
    shuttle_name = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)
    event = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    distance_km = Column(Float, default=0.0)
    passengers = Column(Integer, default=0)
    network_mode = Column(String, default="WIFI_MQTT")
