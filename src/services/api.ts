// ============================================================
// Real API Service Layer — connects to FastAPI backend
// DO NOT modify this to fall back to mockApi silently.
// If backend is offline, functions throw errors so pages
// can show a clear error/offline state.
// ============================================================

import { config } from '../config';
import type {
  Student,
  Seat,
  Shuttle,
  Trip,
  ShuttleRequest,
  VehicleLog,
  DashboardStats,
  ActivityEntry,
  DemandByStop,
  SeatStatus,
  NetworkMode,
} from '../types';

// ============================================================
// CHART DATA — mocked for v1 (replace with real historical API)
// These functions return static demo data until a time-series
// endpoint is added to the backend.
// ============================================================
import {
  passengerChartData,
  tripChartData,
  fareChartData,
  demandChartData,
  demandByStop as mockDemandByStop,
  routeStops as mockRouteStops,
} from '../data/mockData';

export function getPassengerChartData() {
  // TODO: Replace with GET /api/charts/passengers when backend supports it
  return Promise.resolve(structuredClone(passengerChartData));
}

export function getTripChartData() {
  // TODO: Replace with GET /api/charts/trips when backend supports it
  return Promise.resolve(structuredClone(tripChartData));
}

export function getFareChartData() {
  // TODO: Replace with GET /api/charts/fare when backend supports it
  return Promise.resolve(structuredClone(fareChartData));
}

export function getDemandChartData() {
  // TODO: Replace with GET /api/charts/demand when backend supports it
  return Promise.resolve(structuredClone(demandChartData));
}

export function getDemandByStop(): Promise<DemandByStop[]> {
  // TODO: Replace with GET /api/charts/demand-by-stop when backend supports it
  return Promise.resolve(structuredClone(mockDemandByStop));
}

export function getRouteStops() {
  return structuredClone(mockRouteStops);
}

// ============================================================
// HTTP helper
// ============================================================
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${config.apiBaseUrl}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (networkError) {
    throw new Error(`Backend offline — cannot reach ${url}. Start the FastAPI server on port 8000.`);
  }
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`API error ${response.status} ${response.statusText}: ${text}`);
  }
  return response.json() as Promise<T>;
}

// ============================================================
// READ Operations
// ============================================================

export async function getDashboardStats(): Promise<DashboardStats> {
  const data = await apiFetch<{
    activeShuttles: number;
    passengersOnBoard: number;
    availableSeats: number;
    shuttleRequests: number;
    todaysTrips: number;
    todaysRevenue: number;
  }>('/dashboard/stats');

  // Dashboard seat stats — calculated consistently across both shuttles:
  // Total capacity = 60 (30 × 2 shuttles)
  // occupied = passengersOnBoard (counted from seats, not shuttle.passenger_count)
  // available = total_capacity - occupied
  return {
    activeShuttles: data.activeShuttles,
    passengersOnBoard: data.passengersOnBoard,
    availableSeats: data.availableSeats,   // backend already calculates: 60 - occupied
    shuttleRequests: data.shuttleRequests,
    todaysTrips: data.todaysTrips,
    todaysRevenue: data.todaysRevenue,
  };
}

export async function getStudents(): Promise<Student[]> {
  return apiFetch<Student[]>('/students');
}

export async function getStudent(registerNumber: string): Promise<Student | undefined> {
  try {
    return await apiFetch<Student>(`/students/${registerNumber}`);
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('404')) return undefined;
    throw e;
  }
}

export async function getShuttles(): Promise<Shuttle[]> {
  const shuttles = await apiFetch<Shuttle[]>('/shuttles');
  return shuttles;
}

export async function getShuttle(id: string): Promise<Shuttle | undefined> {
  try {
    return await apiFetch<Shuttle>(`/shuttles/${id}`);
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('404')) return undefined;
    throw e;
  }
}

export async function getSeats(shuttleId: string = 'VIT-SHUTTLE-01'): Promise<Seat[]> {
  return apiFetch<Seat[]>(`/shuttles/${shuttleId}/seats`);
}

export async function getSeat(shuttleId: string, seatNumber: number): Promise<Seat | undefined> {
  try {
    return await apiFetch<Seat>(`/shuttles/${shuttleId}/seats/${seatNumber}`);
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('404')) return undefined;
    throw e;
  }
}

export async function getTrips(): Promise<Trip[]> {
  return apiFetch<Trip[]>('/trips');
}

export async function getTrip(id: string): Promise<Trip | undefined> {
  try {
    return await apiFetch<Trip>(`/trips/${id}`);
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes('404')) return undefined;
    throw e;
  }
}

export async function getShuttleRequests(): Promise<ShuttleRequest[]> {
  return apiFetch<ShuttleRequest[]>('/requests');
}

export async function getVehicleLogs(): Promise<VehicleLog[]> {
  return apiFetch<VehicleLog[]>('/vehicle-logs');
}

export async function getVehicleLog(shuttleId: string): Promise<VehicleLog | undefined> {
  const logs = await getVehicleLogs();
  return logs.find((v) => v.shuttleId === shuttleId);
}

export async function getActivities(): Promise<ActivityEntry[]> {
  return apiFetch<ActivityEntry[]>('/dashboard/activities');
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
  return apiFetch<ShuttleRequest>('/requests', {
    method: 'POST',
    body: JSON.stringify({
      student_id: data.studentId,
      pickup_stop: data.pickupStop,
      destination_stop: data.destinationStop,
      class_end_time: data.classEndTime,
    }),
  });
}

export async function simulateSensorReading(
  shuttleId: string,
  seatNumber: number,
  temperature: number,
  pressure: 'HIGH' | 'LOW'
): Promise<{ seat: Seat; detectedStatus: SeatStatus }> {
  const result = await apiFetch<{
    seat_number: number;
    pressure: string;
    temperature: number;
    status: string;
    student_id: string | null;
    gender: string | null;
  }>(`/shuttles/${shuttleId}/seats/${seatNumber}/sensor`, {
    method: 'POST',
    body: JSON.stringify({
      shuttle_id: shuttleId,
      pressure,
      temperature,
    }),
  });

  const detectedStatus = result.status as SeatStatus;
  const seat: Seat = {
    id: `${shuttleId}-${seatNumber}`,
    number: seatNumber,
    status: detectedStatus,
    studentId: result.student_id,
    studentName: null,
    gender: result.gender as ('Male' | 'Female' | null),
    temperature: result.temperature,
    pressure: result.pressure as ('HIGH' | 'LOW'),
    entryTime: null,
    tripId: null,
  };
  return { seat, detectedStatus };
}

export async function toggleNetwork(
  shuttleId: string,
  mode: NetworkMode
): Promise<Shuttle | undefined> {
  await apiFetch(`/shuttles/${shuttleId}/network`, {
    method: 'POST',
    body: JSON.stringify({ network_mode: mode }),
  });
  return getShuttle(shuttleId);
}

export async function simulateEntry(
  shuttleId: string,
  studentId: string,
  seatNumber: number
): Promise<{ seat: Seat; trip: Trip }> {
  const trip = await apiFetch<Trip>('/trips/entry', {
    method: 'POST',
    body: JSON.stringify({
      student_id: studentId,
      shuttle_id: shuttleId,
      seat_number: seatNumber,
    }),
  });
  const seat = await getSeat(shuttleId, seatNumber);
  if (!seat) throw new Error('Seat not found after entry');
  return { seat, trip };
}

export async function simulateExit(
  shuttleId: string,
  seatNumber: number
): Promise<{ seat: Seat; trip: Trip | null }> {
  // Need to find student currently in this seat
  const seat = await getSeat(shuttleId, seatNumber);
  if (!seat || !seat.studentId) throw new Error('No student in this seat');

  const trip = await apiFetch<Trip>('/trips/exit', {
    method: 'POST',
    body: JSON.stringify({
      student_id: seat.studentId,
      shuttle_id: shuttleId,
      seat_number: seatNumber,
      latitude: 12.972000,
      longitude: 79.160000,
    }),
  });
  const updatedSeat = await getSeat(shuttleId, seatNumber);
  return { seat: updatedSeat ?? seat, trip };
}

export async function updateGPS(
  shuttleId: string,
  latitude: number,
  longitude: number
): Promise<void> {
  await apiFetch(`/shuttles/${shuttleId}/gps`, {
    method: 'POST',
    body: JSON.stringify({ latitude, longitude }),
  });
}

export async function updateNetwork(
  shuttleId: string,
  networkMode: NetworkMode
): Promise<void> {
  await apiFetch(`/shuttles/${shuttleId}/network`, {
    method: 'POST',
    body: JSON.stringify({ network_mode: networkMode }),
  });
}

// ============================================================
// LIVE SIMULATION — polls backend instead of mutating local state
// ============================================================
export async function tickSimulation(): Promise<Shuttle[]> {
  return getShuttles();
}

// updateSeat — not needed (sensor endpoint handles it)
export async function updateSeat(
  _shuttleId: string,
  _seatNumber: number,
  _update: Partial<Seat>
): Promise<Seat | undefined> {
  // Use simulateSensorReading instead
  return undefined;
}

// resetMockData — no-op in real API mode
export function resetMockData() {
  // no-op: backend state is managed by SQLite
}
