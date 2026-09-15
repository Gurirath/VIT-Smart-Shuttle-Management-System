import { useState, useEffect } from 'react';
import { Route, MapPin, IndianRupee, CheckCircle, Clock, Receipt, Navigation } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts';
import { getTrips, getFareChartData } from '../services/api';
import type { Trip, PaymentStatus } from '../types';
import Modal from '../components/Modal';
import BackendOffline from '../components/BackendOffline';

export default function TripsAndBilling() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [chartData, setChartData] = useState<{ time: string; fare: number }[]>([]);
  const [selectedTrip, setSelectedTrip] = useState<Trip | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setBackendError(null);
    try {
      const [tripsData, fareData] = await Promise.all([
        getTrips(),
        getFareChartData()
      ]);
      
      // Sort trips by time (most recent first)
      const sortedTrips = [...tripsData].sort((a, b) => b.entryTime.localeCompare(a.entryTime));
      
      setTrips(sortedTrips);
      setChartData(fareData);
    } catch (error) {
      setBackendError(error instanceof Error ? error.message : 'Failed to fetch trips data');
      console.error("Error fetching data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const totalDistance = trips.reduce((sum, trip) => sum + (trip.distance || 0), 0);
  const totalFare = trips.reduce((sum, trip) => sum + (trip.fare || 0), 0);
  const processedCount = trips.filter(t => t.paymentStatus === 'PROCESSED').length;
  const pendingCount = trips.filter(t => t.paymentStatus === 'PENDING').length;

  const handleRowClick = (trip: Trip) => {
    setSelectedTrip(trip);
    setIsModalOpen(true);
  };

  const getStatusColor = (status: PaymentStatus) => {
    switch (status) {
      case 'PROCESSED': return 'bg-green-100 text-green-800';
      case 'PENDING': return 'bg-amber-100 text-amber-800';
      case 'FAILED': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getDuration = (entry: string, exit: string | null) => {
    if (!exit) return 'In Progress';
    try {
      // Mock data uses "HH:MM"
      const [eH, eM] = entry.split(':').map(Number);
      const [xH, xM] = exit.split(':').map(Number);
      if (!isNaN(eH) && !isNaN(xH)) {
        let mins = (xH * 60 + xM) - (eH * 60 + eM);
        if (mins < 0) mins += 24 * 60; // Handle over midnight
        return `${mins} min`;
      }
      return '-';
    } catch (e) {
      return '-';
    }
  };

  const StatCard = ({ title, value, icon: Icon, color }: { title: string, value: string | number, icon: any, color: string }) => (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 flex items-center space-x-4">
      <div className={`p-3 rounded-full ${color}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  );

  if (backendError) {
    return <BackendOffline error={backendError} onRetry={fetchData} />;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Trips & Billing</h1>
        <p className="text-gray-500">Trip history and billing management</p>
      </div>

      {loading ? (
        <div className="text-center py-10 text-gray-500 flex justify-center items-center h-48">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-navy-900"></div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <StatCard title="Today's Trips" value={trips.length} icon={Route} color="bg-blue-100 text-blue-600" />
            <StatCard title="Total Distance" value={`${totalDistance.toFixed(2)} km`} icon={MapPin} color="bg-indigo-100 text-indigo-600" />
            <StatCard title="Total Fare" value={`₹${totalFare.toFixed(2)}`} icon={IndianRupee} color="bg-green-100 text-green-600" />
            <StatCard title="Processed" value={processedCount} icon={CheckCircle} color="bg-emerald-100 text-emerald-600" />
            <StatCard title="Pending" value={pendingCount} icon={Clock} color="bg-amber-100 text-amber-600" />
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Revenue Over Time</h2>
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorFare" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} tickFormatter={(value) => `₹${value}`} />
                  <Tooltip 
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                    formatter={(value: any) => [`₹${value}`, 'Fare']}
                  />
                  <Area type="monotone" dataKey="fare" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorFare)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-500">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-4 font-semibold">Trip ID</th>
                    <th className="px-6 py-4 font-semibold">Student</th>
                    <th className="px-6 py-4 font-semibold">Shuttle</th>
                    <th className="px-6 py-4 font-semibold">Entry Time</th>
                    <th className="px-6 py-4 font-semibold">Exit Time</th>
                    <th className="px-6 py-4 font-semibold">Distance</th>
                    <th className="px-6 py-4 font-semibold">Fare</th>
                    <th className="px-6 py-4 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {trips.map((trip, idx) => (
                    <tr 
                      key={trip.id} 
                      onClick={() => handleRowClick(trip)}
                      className={`cursor-pointer hover:bg-gray-100 border-b border-gray-100 last:border-0 ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}
                    >
                      <td className="px-6 py-4 font-mono font-bold text-gray-900">{trip.id}</td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-gray-900">{trip.studentName}</div>
                        <div className="text-xs text-gray-500">{trip.studentId}</div>
                      </td>
                      <td className="px-6 py-4">{trip.shuttleName}</td>
                      <td className="px-6 py-4">{trip.entryTime}</td>
                      <td className="px-6 py-4">
                        {trip.exitTime ? trip.exitTime : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                            In Progress
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">{trip.distance.toFixed(2)} km</td>
                      <td className="px-6 py-4">₹{trip.fare.toFixed(2)}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(trip.paymentStatus)}`}>
                          {trip.paymentStatus}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {selectedTrip && (
        <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Trip Details">
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-gray-900 flex items-center mb-3">
                <Receipt className="w-4 h-4 mr-2" />
                Trip Information
              </h3>
              <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
                <div>
                  <p className="text-xs text-gray-500">Trip ID</p>
                  <p className="font-mono font-semibold text-gray-900">{selectedTrip.id}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Shuttle</p>
                  <p className="font-medium text-gray-900">{selectedTrip.shuttleName}</p>
                </div>
                <div className="col-span-2">
                  <p className="text-xs text-gray-500">Student</p>
                  <p className="font-medium text-gray-900">{selectedTrip.studentName} ({selectedTrip.studentId})</p>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 flex items-center mb-3">
                <Navigation className="w-4 h-4 mr-2" />
                Route Details
              </h3>
              <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
                <div>
                  <p className="text-xs text-gray-500">Entry Location</p>
                  <p className="font-medium text-gray-900">{selectedTrip.entryLocation}</p>
                  <p className="text-xs text-gray-400 mt-1">{selectedTrip.entryGps.lat.toFixed(6)}, {selectedTrip.entryGps.lng.toFixed(6)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Exit Location</p>
                  {selectedTrip.exitLocation ? (
                    <>
                      <p className="font-medium text-gray-900">{selectedTrip.exitLocation}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {selectedTrip.exitGps?.lat.toFixed(6)}, {selectedTrip.exitGps?.lng.toFixed(6)}
                      </p>
                    </>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                      In Progress
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 flex items-center mb-3">
                <Clock className="w-4 h-4 mr-2" />
                Timing
              </h3>
              <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
                <div>
                  <p className="text-xs text-gray-500">Entry Time</p>
                  <p className="font-medium text-gray-900">{selectedTrip.entryTime}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Exit Time</p>
                  {selectedTrip.exitTime ? (
                    <p className="font-medium text-gray-900">{selectedTrip.exitTime}</p>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                      In Progress
                    </span>
                  )}
                </div>
                <div className="col-span-2">
                  <p className="text-xs text-gray-500">Duration</p>
                  <p className="font-medium text-gray-900">
                    {getDuration(selectedTrip.entryTime, selectedTrip.exitTime)}
                  </p>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 flex items-center mb-3">
                <IndianRupee className="w-4 h-4 mr-2" />
                Billing
              </h3>
              <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
                <div>
                  <p className="text-xs text-gray-500">Distance</p>
                  <p className="font-medium text-gray-900">{selectedTrip.distance.toFixed(2)} km</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Fare</p>
                  <p className="font-medium text-gray-900">₹{selectedTrip.fare.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Payment Method</p>
                  <p className="font-medium text-gray-900">Fee Account</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Payment Status</p>
                  <span className={`inline-flex items-center mt-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(selectedTrip.paymentStatus)}`}>
                    {selectedTrip.paymentStatus}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
