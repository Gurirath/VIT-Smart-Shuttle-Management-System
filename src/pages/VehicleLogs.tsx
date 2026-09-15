import React, { useState, useEffect } from 'react';
import { getVehicleLogs, getVehicleLog } from '../services/api';
import type { VehicleLog, NetworkMode } from '../types';
import { Route, MapPin, Fuel, Users, BarChart3, Wifi, Bus, Signal, Radio, Activity, Loader2 } from 'lucide-react';
import BackendOffline from '../components/BackendOffline';

const VehicleLogs: React.FC = () => {
  const [logs, setLogs] = useState<VehicleLog[]>([]);
  const [selectedShuttleId, setSelectedShuttleId] = useState<string>('');
  const [currentLog, setCurrentLog] = useState<VehicleLog | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [backendError, setBackendError] = useState<string | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    setBackendError(null);
    try {
      const allLogs = await getVehicleLogs();
      setLogs(allLogs);
      
      if (allLogs.length > 0) {
         setSelectedShuttleId(allLogs[0].shuttleId);
      }
    } catch (error) {
      setBackendError(error instanceof Error ? error.message : 'Failed to fetch logs');
      console.error("Failed to fetch logs", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  useEffect(() => {
    const fetchCurrentLog = async () => {
      if (selectedShuttleId) {
        setLoading(true);
        try {
          const log = await getVehicleLog(selectedShuttleId);
          if (log) {
            setCurrentLog(log);
          }
        } catch (error) {
          console.error("Failed to fetch current log", error);
        } finally {
          setLoading(false);
        }
      }
    };
    fetchCurrentLog();
  }, [selectedShuttleId]);

  if (backendError) {
    return <BackendOffline error={backendError} onRetry={fetchLogs} />;
  }

  if (loading && !currentLog) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    );
  }

  if (!currentLog) {
    return (
      <div className="p-6 bg-gray-50 min-h-screen">
        <h1 className="text-2xl font-bold text-gray-900">Vehicle Logs</h1>
        <p className="text-gray-500">Failed to load vehicle logs.</p>
      </div>
    );
  }

  const getOccupancyRingColor = (occupancy: number) => {
    if (occupancy > 60) return 'text-green-500';
    if (occupancy >= 40) return 'text-amber-500';
    return 'text-red-500';
  };

  const getNetworkBadge = (mode: NetworkMode) => {
    switch (mode) {
      case 'WIFI_MQTT':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200">WiFi / MQTT</span>;
      case 'GSM_FALLBACK':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">GSM Fallback</span>;
      case 'OFFLINE':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-200">Offline</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 border border-gray-200">{mode}</span>;
    }
  };

  const getEventTextColor = (eventText: string) => {
    const text = eventText.toLowerCase();
    if (text.includes('started') || text.includes('completed') || text.includes('restored')) return 'text-green-600 font-medium';
    if (text.includes('entered') || text.includes('exited')) return 'text-blue-600 font-medium';
    if (text.includes('disconnected')) return 'text-red-600 font-medium';
    if (text.includes('fallback')) return 'text-amber-600 font-medium';
    return 'text-gray-600';
  };

  // Calculate network stats
  const wifiUptime = currentLog.networkAvailability;
  const gsmFallbackCount = currentLog.events.filter(e => e.network === 'GSM_FALLBACK').length;
  const offlineCount = currentLog.events.filter(e => e.network === 'OFFLINE').length;

  return (
    <div className="p-6 bg-gray-50 min-h-screen space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Vehicle Logs</h1>
          <p className="text-gray-500 mt-1">Vehicle monitoring and event history</p>
        </div>

        {/* Shuttle selector */}
        <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1">
          {logs.map((log) => (
            <button
              key={log.shuttleId}
              onClick={() => setSelectedShuttleId(log.shuttleId)}
              className={`flex items-center px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                selectedShuttleId === log.shuttleId
                  ? 'bg-blue-50 text-blue-700 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Bus className="w-4 h-4 mr-2" />
              {log.shuttleId}
            </button>
          ))}
        </div>
      </div>

      {/* Vehicle Statistics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 flex items-center">
          <div className="p-3 rounded-lg bg-blue-50 text-blue-600 mr-4">
            <Route className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Total Trips</p>
            <p className="text-2xl font-semibold text-gray-900">{currentLog.totalTrips}</p>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 flex items-center">
          <div className="p-3 rounded-lg bg-indigo-50 text-indigo-600 mr-4">
            <MapPin className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Total Distance</p>
            <p className="text-2xl font-semibold text-gray-900">{currentLog.totalDistance} km</p>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 flex items-center">
          <div className="p-3 rounded-lg bg-emerald-50 text-emerald-600 mr-4">
            <Fuel className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Fuel Consumed</p>
            <p className="text-2xl font-semibold text-gray-900">{currentLog.fuelConsumed} L</p>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 flex items-center">
          <div className="p-3 rounded-lg bg-purple-50 text-purple-600 mr-4">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Passengers Served</p>
            <p className="text-2xl font-semibold text-gray-900">{currentLog.passengersServed}</p>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 flex items-center">
          <div className="p-3 rounded-lg bg-orange-50 text-orange-600 mr-4">
            <BarChart3 className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Average Occupancy</p>
            <p className="text-2xl font-semibold text-gray-900">{currentLog.averageOccupancy}%</p>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 flex items-center">
          <div className="p-3 rounded-lg bg-cyan-50 text-cyan-600 mr-4">
            <Wifi className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Network Availability</p>
            <p className="text-2xl font-semibold text-gray-900">{currentLog.networkAvailability}%</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Occupancy Visual */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6 flex items-center">
            <Users className="w-5 h-5 mr-2 text-gray-500" /> Average Occupancy
          </h2>
          <div className="flex flex-col items-center justify-center">
            <div className="relative w-48 h-48 flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                {/* Background circle */}
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  fill="transparent"
                  stroke="currentColor"
                  strokeWidth="8"
                  className="text-gray-100"
                />
                {/* Progress circle */}
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  fill="transparent"
                  stroke="currentColor"
                  strokeWidth="8"
                  strokeDasharray={`${(currentLog.averageOccupancy / 100) * 251.2} 251.2`}
                  className={`${getOccupancyRingColor(currentLog.averageOccupancy)} transition-all duration-1000 ease-out`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute flex flex-col items-center justify-center text-center">
                <span className="text-4xl font-bold text-gray-900">{currentLog.averageOccupancy}%</span>
                <span className="text-sm text-gray-500 mt-1">Occupancy</span>
              </div>
            </div>
            
            <div className="flex justify-center mt-6 space-x-6 text-sm text-gray-600 font-medium">
              <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-green-500 mr-2"></span> &gt;60%</div>
              <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-amber-500 mr-2"></span> 40-60%</div>
              <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-red-500 mr-2"></span> &lt;40%</div>
            </div>
          </div>
        </div>

        {/* Network Status Summary */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-gray-500" /> Network Status
          </h2>
          
          <div className="space-y-6">
            <div>
              <div className="flex justify-between items-end mb-2">
                <span className="text-sm font-medium text-gray-600">Availability</span>
                <span className="text-2xl font-bold text-gray-900">{wifiUptime}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div className="bg-green-500 h-2.5 rounded-full" style={{ width: `${wifiUptime}%` }}></div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-6">
              <div className="border border-gray-100 bg-gray-50 rounded-lg p-4">
                <div className="flex items-center text-amber-600 mb-1">
                  <Signal className="w-4 h-4 mr-1.5" />
                  <span className="text-sm font-semibold">GSM Fallback</span>
                </div>
                <div className="text-2xl font-bold text-gray-900">{gsmFallbackCount} <span className="text-sm font-normal text-gray-500">events</span></div>
              </div>
              
              <div className="border border-gray-100 bg-gray-50 rounded-lg p-4">
                <div className="flex items-center text-red-600 mb-1">
                  <Radio className="w-4 h-4 mr-1.5" />
                  <span className="text-sm font-semibold">Offline</span>
                </div>
                <div className="text-2xl font-bold text-gray-900">{offlineCount} <span className="text-sm font-normal text-gray-500">events</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Event History Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-900">Trip History</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b border-gray-200">
              <tr>
                <th scope="col" className="px-6 py-3 font-medium">Time</th>
                <th scope="col" className="px-6 py-3 font-medium">Event</th>
                <th scope="col" className="px-6 py-3 font-medium">Location</th>
                <th scope="col" className="px-6 py-3 font-medium">Distance</th>
                <th scope="col" className="px-6 py-3 font-medium">Passengers</th>
                <th scope="col" className="px-6 py-3 font-medium">Network</th>
              </tr>
            </thead>
            <tbody>
              {currentLog.events.map((event, index) => (
                <tr key={event.id} className={`${index % 2 === 0 ? 'bg-white' : 'bg-gray-50'} border-b border-gray-100 last:border-0 hover:bg-gray-100 transition-colors`}>
                  <td className="px-6 py-4 font-mono font-semibold text-gray-700 whitespace-nowrap">
                    {event.time}
                  </td>
                  <td className={`px-6 py-4 ${getEventTextColor(event.event)}`}>
                    {event.event}
                  </td>
                  <td className="px-6 py-4 text-gray-600 font-medium">
                    {event.location}
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    {event.distance} km
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    {event.passengers}
                  </td>
                  <td className="px-6 py-4">
                    {getNetworkBadge(event.network)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {currentLog.events.length === 0 && (
            <div className="p-8 text-center text-gray-500">
              No events found for this log.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default VehicleLogs;
