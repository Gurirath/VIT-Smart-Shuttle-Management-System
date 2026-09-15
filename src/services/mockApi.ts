// ============================================================
// Mock API Service Layer
// Replace this file with real API calls when backend is ready
// ============================================================

import type {
  Student,
  Seat,
  Shuttle,
  Trip,
  ShuttleRequest,
  VehicleLog,
  DashboardStats,
  ActivityEntry,
  SeatStatus,
  NetworkMode,
  DemandByStop,
} from '../types';

import {
  mockStudents,
  mockShuttles,
  mockTrips,
  mockShuttleRequests,
  mockVehicleLogs,
  mockActivities,
  passengerChartData,
  tripChartData,
  fareChartData,
  demandChartData,
  demandByStop,
  routeStops,
} from '../data/mockData';

// Simulated network delay
const delay = (ms: number = 200) => new Promise((resolve) => setTimeout(resolve, ms));

// In-memory mutable state (cloned from mock data)
let students = structuredClone(mockStudents);
let shuttles = structuredClone(mockShuttles);
let trips = structuredClone(mockTrips);
let shuttleRequests = structuredClone(mockShuttleRequests);
let vehicleLogs = structuredClone(mockVehicleLogs);
let activities = structuredClone(mockActivities);

// ============================================================
// READ Operations
// ============================================================

export async function getStudents(): Promise<Student[]> {
  await delay();
  return structuredClone(students);
}

export async function getStudent(registerNumber: string): Promise<Student | undefined> {
  await delay();
  return structuredClone(students.find((s) => s.registerNumber === registerNumber));
}

export async function getShuttles(): Promise<Shuttle[]> {
  await delay();
  return structuredClone(shuttles);
}

export async function getShuttle(id: string): Promise<Shuttle | undefined> {
  await delay();
  return structuredClone(shuttles.find((s) => s.id === id));
}

export async function getSeats(shuttleId: string = 'shuttle-01'): Promise<Seat[]> {
  await delay();
  const shuttle = shuttles.find((s) => s.id === shuttleId);
  return structuredClone(shuttle?.seats ?? []);
}

export async function getSeat(shuttleId: string, seatNumber: number): Promise<Seat | undefined> {
  await delay();
  const shuttle = shuttles.find((s) => s.id === shuttleId);
  return structuredClone(shuttle?.seats.find((s) => s.number === seatNumber));
}

export async function getTrips(): Promise<Trip[]> {
  await delay();
  return structuredClone(trips);
}

export async function getTrip(id: string): Promise<Trip | undefined> {
  await delay();
  return structuredClone(trips.find((t) => t.id === id));
}

export async function getShuttleRequests(): Promise<ShuttleRequest[]> {
  await delay();
  return structuredClone(shuttleRequests);
}

export async function getVehicleLogs(): Promise<VehicleLog[]> {
  await delay();
  return structuredClone(vehicleLogs);
}

export async function getVehicleLog(shuttleId: string): Promise<VehicleLog | undefined> {
  await delay();
  return structuredClone(vehicleLogs.find((v) => v.shuttleId === shuttleId));
}

export async function getDashboardStats(): Promise<DashboardStats> {
  await delay();
  const activeShuttles = shuttles.filter((s) => s.status === 'RUNNING').length;
  const passengersOnBoard = shuttles.reduce((sum, s) => sum + s.passengers, 0);
  const availableSeats = shuttles.reduce((sum, s) => sum + (s.capacity - s.passengers), 0);
  const totalRequests = shuttleRequests.length;
  const todaysTrips = 47;
  const todaysRevenue = 1240;

  return {
    activeShuttles,
    passengersOnBoard,
    availableSeats,
    shuttleRequests: totalRequests,
    todaysTrips,
    todaysRevenue,
  };
}

export async function getActivities(): Promise<ActivityEntry[]> {
  await delay();
  return structuredClone(activities);
}

export async function getPassengerChartData() {
  await delay();
  return structuredClone(passengerChartData);
}

export async function getTripChartData() {
  await delay();
  return structuredClone(tripChartData);
}

export async function getFareChartData() {
  await delay();
  return structuredClone(fareChartData);
}

export async function getDemandChartData() {
  await delay();
  return structuredClone(demandChartData);
}

export async function getDemandByStop(): Promise<DemandByStop[]> {
  await delay();
  return structuredClone(demandByStop);
}

export function getRouteStops() {
  return structuredClone(routeStops);
}

// ============================================================
// MUTATION Operations
// ============================================================

export async function requestShuttle(data: {
  studentId: string;
  pickupStop: string;
  destinationStop: string;
  classEndTime: string;
}): Promise<ShuttleRequest> {
  await delay(300);
  const student = students.find((s) => s.registerNumber === data.studentId);
  const newRequest: ShuttleRequest = {
    id: `REQ-${String(shuttleRequests.length + 1).padStart(3, '0')}`,
    studentId: data.studentId,
    studentName: student?.name ?? data.studentId,
    pickupStop: data.pickupStop,
    destinationStop: data.destinationStop,
    classEndTime: data.classEndTime,
    requestTime: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
    status: 'PENDING',
  };
  shuttleRequests = [newRequest, ...shuttleRequests];
  return structuredClone(newRequest);
}

export async function updateSeat(
  shuttleId: string,
  seatNumber: number,
  update: Partial<Seat>
): Promise<Seat | undefined> {
  await delay(100);
  const shuttle = shuttles.find((s) => s.id === shuttleId);
  if (!shuttle) return undefined;
  const seat = shuttle.seats.find((s) => s.number === seatNumber);
  if (!seat) return undefined;
  Object.assign(seat, update);
  return structuredClone(seat);
}

export async function simulateSensorReading(
  shuttleId: string,
  seatNumber: number,
  temperature: number,
  pressure: 'HIGH' | 'LOW'
): Promise<{ seat: Seat; detectedStatus: SeatStatus }> {
  await delay(100);

  let detectedStatus: SeatStatus = 'AVAILABLE';
  if (pressure === 'LOW') {
    detectedStatus = 'AVAILABLE';
  } else if (temperature >= 34.0 && temperature <= 42.0) {
    detectedStatus = 'OCCUPIED';
  } else {
    detectedStatus = 'OBJECT';
  }

  const shuttle = shuttles.find((s) => s.id === shuttleId);
  if (!shuttle) throw new Error('Shuttle not found');

  const seat = shuttle.seats.find((s) => s.number === seatNumber);
  if (!seat) throw new Error('Seat not found');

  seat.status = detectedStatus;
  seat.temperature = temperature;
  seat.pressure = pressure;

  if (detectedStatus === 'AVAILABLE') {
    seat.studentId = null;
    seat.studentName = null;
    seat.gender = null;
    seat.entryTime = null;
    seat.tripId = null;
  }

  // Update passenger count
  shuttle.passengers = shuttle.seats.filter((s) => s.status === 'OCCUPIED').length;

  return { seat: structuredClone(seat), detectedStatus };
}

export async function toggleNetwork(
  shuttleId: string,
  mode: NetworkMode
): Promise<Shuttle | undefined> {
  await delay(100);
  const shuttle = shuttles.find((s) => s.id === shuttleId);
  if (!shuttle) return undefined;
  shuttle.network = mode;

  // Add activity
  const networkLabel = mode === 'WIFI_MQTT' ? 'WiFi + MQTT restored' : mode === 'GSM_FALLBACK' ? 'GSM fallback activated' : 'Network offline';
  activities = [
    {
      id: `act-${Date.now()}`,
      message: `${shuttle.name}: ${networkLabel}`,
      timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
      type: 'network',
    },
    ...activities,
  ];

  return structuredClone(shuttle);
}

export async function simulateEntry(
  shuttleId: string,
  studentId: string,
  seatNumber: number
): Promise<{ seat: Seat; trip: Trip }> {
  await delay(200);
  const shuttle = shuttles.find((s) => s.id === shuttleId);
  if (!shuttle) throw new Error('Shuttle not found');

  const seat = shuttle.seats.find((s) => s.number === seatNumber);
  if (!seat) throw new Error('Seat not found');

  const student = students.find((s) => s.registerNumber === studentId);
  if (!student) throw new Error('Student not found');

  const tripId = `TRIP-${String(trips.length + 1).padStart(3, '0')}`;
  const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });

  // Update seat
  seat.status = 'OCCUPIED';
  seat.studentId = studentId;
  seat.studentName = student.name;
  seat.gender = student.gender;
  seat.temperature = +(36.1 + Math.random() * 1.1).toFixed(1);
  seat.pressure = 'HIGH';
  seat.entryTime = now;
  seat.tripId = tripId;

  // Update shuttle
  shuttle.passengers = shuttle.seats.filter((s) => s.status === 'OCCUPIED').length;

  // Update student
  student.status = 'ON_SHUTTLE';
  student.currentShuttle = shuttle.name;
  student.currentSeat = seatNumber;
  student.tripId = tripId;

  // Create trip
  const trip: Trip = {
    id: tripId,
    studentId,
    studentName: student.name,
    shuttleId,
    shuttleName: shuttle.name,
    entryTime: now,
    exitTime: null,
    entryLocation: 'Main Gate',
    exitLocation: null,
    entryGps: { lat: shuttle.latitude, lng: shuttle.longitude },
    exitGps: null,
    distance: 0,
    fare: 0,
    paymentStatus: 'PENDING',
  };
  trips = [trip, ...trips];

  // Add activity
  activities = [
    {
      id: `act-${Date.now()}`,
      message: `${studentId} entered ${shuttle.name} (Seat ${seatNumber})`,
      timestamp: now,
      type: 'entry',
    },
    ...activities,
  ];

  return { seat: structuredClone(seat), trip: structuredClone(trip) };
}

export async function simulateExit(
  shuttleId: string,
  seatNumber: number
): Promise<{ seat: Seat; trip: Trip | null }> {
  await delay(200);
  const shuttle = shuttles.find((s) => s.id === shuttleId);
  if (!shuttle) throw new Error('Shuttle not found');

  const seat = shuttle.seats.find((s) => s.number === seatNumber);
  if (!seat) throw new Error('Seat not found');

  const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });

  // Find and complete the trip
  let completedTrip: Trip | null = null;
  if (seat.tripId) {
    const trip = trips.find((t) => t.id === seat.tripId);
    if (trip) {
      trip.exitTime = now;
      trip.exitLocation = 'Academic Block';
      trip.exitGps = { lat: 12.969574, lng: 79.155890 };
      trip.distance = +(0.5 + Math.random() * 1).toFixed(2);
      trip.fare = +(trip.distance * 5).toFixed(2);
      trip.paymentStatus = 'PROCESSED';
      completedTrip = structuredClone(trip);
    }
  }

  // Update student
  if (seat.studentId) {
    const student = students.find((s) => s.registerNumber === seat.studentId);
    if (student) {
      student.status = 'ON_CAMPUS';
      student.currentShuttle = null;
      student.currentSeat = null;
      student.tripId = null;
      student.tripsToday += 1;
      if (completedTrip) {
        student.totalDistance += completedTrip.distance;
        student.totalFare += completedTrip.fare;
      }
    }
  }

  // Add activity
  activities = [
    {
      id: `act-${Date.now()}`,
      message: `${seat.studentId ?? 'Unknown'} exited ${shuttle.name} (Seat ${seatNumber})`,
      timestamp: now,
      type: 'exit',
    },
    ...activities,
  ];

  // Clear seat
  seat.status = 'AVAILABLE';
  seat.studentId = null;
  seat.studentName = null;
  seat.gender = null;
  seat.temperature = null;
  seat.pressure = null;
  seat.entryTime = null;
  seat.tripId = null;

  // Update shuttle
  shuttle.passengers = shuttle.seats.filter((s) => s.status === 'OCCUPIED').length;

  return { seat: structuredClone(seat), trip: completedTrip };
}

// ============================================================
// LIVE SIMULATION (GPS drift, route progress)
// ============================================================
export async function tickSimulation(): Promise<Shuttle[]> {
  for (const shuttle of shuttles) {
    if (shuttle.status === 'RUNNING') {
      // Small GPS drift
      shuttle.latitude += (Math.random() - 0.5) * 0.0002;
      shuttle.longitude += (Math.random() - 0.5) * 0.0002;

      // Route progress
      if (shuttle.routeProgress < 100) {
        shuttle.routeProgress = Math.min(100, shuttle.routeProgress + Math.random() * 0.8);
      } else {
        shuttle.routeProgress = 0; // Reset for loop
      }

      // Distance
      shuttle.distance = +(shuttle.distance + Math.random() * 0.01).toFixed(2);
      shuttle.estimatedFare = +(shuttle.distance * 5).toFixed(2);
    }
  }
  return structuredClone(shuttles);
}

// ============================================================
// RESET (for development)
// ============================================================
export function resetMockData() {
  students = structuredClone(mockStudents);
  shuttles = structuredClone(mockShuttles);
  trips = structuredClone(mockTrips);
  shuttleRequests = structuredClone(mockShuttleRequests);
  vehicleLogs = structuredClone(mockVehicleLogs);
  activities = structuredClone(mockActivities);
}
