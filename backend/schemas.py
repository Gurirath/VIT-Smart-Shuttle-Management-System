from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ------- Student -------
class StudentBase(BaseModel):
    register_number: str
    name: str
    gender: str
    department: str
    fee_account: str
    payment_status: str = "ACTIVE"

class StudentCreate(StudentBase):
    pass

class StudentResponse(BaseModel):
    id: str
    registerNumber: str
    name: str
    gender: str
    department: str
    status: str
    currentShuttle: Optional[str]
    currentSeat: Optional[int]
    tripsToday: int
    totalDistance: float
    totalFare: float
    paymentStatus: str
    tripId: Optional[str]
    model_config = {"from_attributes": True}

# ------- Shuttle -------
class SeatResponse(BaseModel):
    id: str
    number: int
    status: str
    studentId: Optional[str]
    studentName: Optional[str]
    gender: Optional[str]
    temperature: Optional[float]
    pressure: Optional[str]
    entryTime: Optional[str]
    tripId: Optional[str]
    model_config = {"from_attributes": True}

class ShuttleResponse(BaseModel):
    id: str
    name: str
    status: str
    passengers: int
    capacity: int
    latitude: float
    longitude: float
    routeProgress: float
    network: str
    currentTrip: str
    distance: float
    estimatedFare: float
    currentRoute: str
    seats: List[SeatResponse] = []
    model_config = {"from_attributes": True}

# ------- Sensor -------
class SensorRequest(BaseModel):
    shuttle_id: str
    pressure: str  # HIGH / LOW
    temperature: float

class SensorResponse(BaseModel):
    seat_number: int
    pressure: str
    temperature: float
    status: str
    student_id: Optional[str]
    gender: Optional[str]

# ------- GPS -------
class GPSUpdate(BaseModel):
    latitude: float
    longitude: float

# ------- Network -------
class NetworkUpdate(BaseModel):
    network_mode: str  # WIFI_MQTT / GSM_FALLBACK / OFFLINE

# ------- Trip -------
class TripEntryRequest(BaseModel):
    student_id: str
    shuttle_id: str
    seat_number: int
    latitude: float = 12.969574
    longitude: float = 79.155987

class TripExitRequest(BaseModel):
    student_id: str
    shuttle_id: str
    seat_number: int
    latitude: float = 12.972000
    longitude: float = 79.160000
    distance_km: Optional[float] = None
    fare: Optional[float] = None

class TripResponse(BaseModel):
    id: str
    studentId: str
    studentName: str
    shuttleId: str
    shuttleName: str
    entryTime: str
    exitTime: Optional[str]
    entryLocation: str
    exitLocation: Optional[str]
    entryGps: dict
    exitGps: Optional[dict]
    distance: float
    fare: float
    paymentStatus: str
    model_config = {"from_attributes": True}

# ------- ShuttleRequest -------
class ShuttleRequestCreate(BaseModel):
    student_id: str
    pickup_stop: str
    destination_stop: str
    class_end_time: str

class ShuttleRequestResponse(BaseModel):
    id: str
    studentId: str
    studentName: str
    pickupStop: str
    destinationStop: str
    classEndTime: str
    requestTime: str
    status: str
    model_config = {"from_attributes": True}

# ------- Vehicle Log -------
class VehicleEventResponse(BaseModel):
    id: str
    time: str
    event: str
    location: str
    distance: float
    passengers: int
    network: str

class VehicleLogResponse(BaseModel):
    id: str
    shuttleId: str
    shuttleName: str
    totalTrips: int
    totalDistance: float
    fuelConsumed: float
    passengersServed: int
    averageOccupancy: float
    networkAvailability: float
    events: List[VehicleEventResponse]

# ------- Dashboard -------
class DashboardStats(BaseModel):
    activeShuttles: int
    passengersOnBoard: int
    availableSeats: int
    shuttleRequests: int
    todaysTrips: int
    todaysRevenue: float

# ------- Activity -------
class ActivityEntry(BaseModel):
    id: str
    message: str
    timestamp: str
    type: str
