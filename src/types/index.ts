// ============================================================
// Core Data Types for VIT Smart Shuttle System
// ============================================================

export type ShuttleStatus = 'RUNNING' | 'IDLE' | 'MAINTENANCE';
export type SeatStatus = 'AVAILABLE' | 'OCCUPIED' | 'OBJECT';
export type NetworkMode = 'WIFI_MQTT' | 'GSM_FALLBACK' | 'OFFLINE';
export type PaymentStatus = 'PROCESSED' | 'PENDING' | 'FAILED';
export type Gender = 'Male' | 'Female';
export type StudentStatus = 'ON_SHUTTLE' | 'OFF_CAMPUS' | 'ON_CAMPUS';

export interface Student {
  id: string;
  registerNumber: string;
  name: string;
  gender: Gender;
  department: string;
  status: StudentStatus;
  currentShuttle: string | null;
  currentSeat: number | null;
  tripsToday: number;
  totalDistance: number;
  totalFare: number;
  paymentStatus: PaymentStatus;
  tripId: string | null;
}

export interface Seat {
  id: string;
  number: number;
  status: SeatStatus;
  studentId: string | null;
  studentName: string | null;
  gender: Gender | null;
  temperature: number | null;
  pressure: 'HIGH' | 'LOW' | null;
  entryTime: string | null;
  tripId: string | null;
}

export interface Shuttle {
  id: string;
  name: string;
  status: ShuttleStatus;
  passengers: number;
  capacity: number;
  latitude: number;
  longitude: number;
  routeProgress: number;
  network: NetworkMode;
  currentTrip: string;
  distance: number;
  estimatedFare: number;
  currentRoute: string;
  seats: Seat[];
}

export interface Trip {
  id: string;
  studentId: string;
  studentName: string;
  shuttleId: string;
  shuttleName: string;
  entryTime: string;
  exitTime: string | null;
  entryLocation: string;
  exitLocation: string | null;
  entryGps: { lat: number; lng: number };
  exitGps: { lat: number; lng: number } | null;
  distance: number;
  fare: number;
  paymentStatus: PaymentStatus;
}

export interface ShuttleRequest {
  id: string;
  studentId: string;
  studentName: string;
  pickupStop: string;
  destinationStop: string;
  classEndTime: string;
  requestTime: string;
  status: 'PENDING' | 'ACKNOWLEDGED' | 'FULFILLED';
}

export interface VehicleLog {
  id: string;
  shuttleId: string;
  shuttleName: string;
  totalTrips: number;
  totalDistance: number;
  fuelConsumed: number;
  passengersServed: number;
  averageOccupancy: number;
  networkAvailability: number;
  events: VehicleEvent[];
}

export interface VehicleEvent {
  id: string;
  time: string;
  event: string;
  location: string;
  distance: number;
  passengers: number;
  network: NetworkMode;
}

export interface SensorReading {
  seatNumber: number;
  temperature: number;
  pressure: 'HIGH' | 'LOW';
  networkMode: NetworkMode;
}

export interface DashboardStats {
  activeShuttles: number;
  passengersOnBoard: number;
  availableSeats: number;
  shuttleRequests: number;
  todaysTrips: number;
  todaysRevenue: number;
}

export interface ActivityEntry {
  id: string;
  message: string;
  timestamp: string;
  type: 'entry' | 'exit' | 'detection' | 'network' | 'request' | 'system';
}

export interface DemandByStop {
  stop: string;
  count: number;
}

export interface RouteStop {
  id: string;
  name: string;
  x: number;
  y: number;
}
