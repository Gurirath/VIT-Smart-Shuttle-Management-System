import React, { useState, useEffect, useCallback } from 'react';
import { 
  Bus, Users, Armchair, MessageSquare, Route, IndianRupee, Activity, Play, Pause, Circle 
} from 'lucide-react';
import { 
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer 
} from 'recharts';
import type { 
  DashboardStats, Shuttle, ActivityEntry, ShuttleStatus, NetworkMode 
} from '../types';
import { 
  getDashboardStats, getShuttles, getActivities, getPassengerChartData, getTripChartData, tickSimulation 
} from '../services/api';
import StatCard from '../components/StatCard';
import BackendOffline from '../components/BackendOffline';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [shuttles, setShuttles] = useState<Shuttle[]>([]);
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [passengerData, setPassengerData] = useState<{ time: string; passengers: number }[]>([]);
  const [tripData, setTripData] = useState<{ time: string; trips: number }[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [backendError, setBackendError] = useState<string | null>(null);

  const loadInitialData = useCallback(async () => {
    try {
      const [
        statsData,
        shuttlesData,
        activitiesData,
        pData,
        tData
      ] = await Promise.all([
        getDashboardStats(),
        getShuttles(),
        getActivities(),
        getPassengerChartData(),
        getTripChartData()
      ]);

      setStats(statsData);
      setShuttles(shuttlesData);
      setActivities(activitiesData);
      setPassengerData(pData);
      setTripData(tData);
      setLastUpdated(new Date());
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to load dashboard data';
      setBackendError(msg);
      console.error("Failed to load dashboard data:", error);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  useEffect(() => {
    if (isPaused) return;

    const interval = setInterval(async () => {
      try {
        const updatedShuttles = await tickSimulation();
        setShuttles(updatedShuttles);
        const updatedStats = await getDashboardStats();
        setStats(updatedStats);
        const updatedActivities = await getActivities();
        setActivities(updatedActivities);
        setLastUpdated(new Date());
      } catch (error) {
        console.error("Failed to update simulation:", error);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isPaused]);

  const getActivityColor = (type: string) => {
    switch (type) {
      case 'entry': return 'text-green-500';
      case 'exit': return 'text-blue-500';
      case 'detection': return 'text-amber-500';
      case 'network': return 'text-purple-500';
      case 'request': return 'text-orange-500';
      case 'system':
      default: return 'text-gray-500';
    }
  };

  const getStatusBadge = (status: ShuttleStatus) => {
    switch (status) {
      case 'RUNNING':
        return <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full">RUNNING</span>;
      case 'IDLE':
        return <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-full">IDLE</span>;
      case 'MAINTENANCE':
        return <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-medium rounded-full">MAINTENANCE</span>;
      default:
        return null;
    }
  };

  const getNetworkBadge = (network: NetworkMode) => {
    switch (network) {
      case 'WIFI_MQTT':
        return <span className="text-sm text-green-600 flex items-center gap-1"><Activity size={14} /> WiFi Connected</span>;
      case 'GSM_FALLBACK':
        return <span className="text-sm text-blue-600 flex items-center gap-1"><Activity size={14} /> GSM Fallback</span>;
      case 'OFFLINE':
        return <span className="text-sm text-red-600 flex items-center gap-1"><Activity size={14} /> Offline</span>;
      default:
        return null;
    }
  };

  if (backendError) return <BackendOffline error={backendError} onRetry={() => { setBackendError(null); loadInitialData(); }} />;
  if (!stats) return <div className="p-8">Loading dashboard...</div>;

  return (
    <div className="p-6 bg-gray-50 min-h-screen font-sans">
      {/* Header section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">VIT Smart Shuttle</h1>
          <p className="text-sm text-gray-500">Campus Transportation Management</p>
        </div>
        <div className="flex items-center gap-4 mt-4 md:mt-0">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-full shadow-sm">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
            </span>
            <span className="text-sm font-medium text-gray-700">System Online</span>
          </div>
          <div className="text-xs text-gray-500">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
          <button 
            onClick={() => setIsPaused(!isPaused)}
            className="flex items-center gap-1 px-3 py-1.5 bg-white border border-gray-200 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            {isPaused ? <Play size={16} /> : <Pause size={16} />}
            {isPaused ? "Resume" : "Pause Live Updates"}
          </button>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 mb-6">
        <StatCard title="Active Shuttles" value={stats.activeShuttles} icon={Bus} color="text-blue-600" />
        <StatCard title="Passengers On Board" value={stats.passengersOnBoard} icon={Users} color="text-green-600" />
        <StatCard title="Available Seats" value={stats.availableSeats} icon={Armchair} color="text-gray-600" />
        <StatCard title="Shuttle Requests" value={stats.shuttleRequests} icon={MessageSquare} color="text-purple-600" />
        <StatCard title="Today's Trips" value={stats.todaysTrips} icon={Route} color="text-orange-600" />
        <StatCard title="Today's Revenue" value={`₹${stats.todaysRevenue}`} icon={IndianRupee} color="text-emerald-600" />
      </div>

      {/* Live Shuttle Status */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Live Shuttle Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {shuttles.map(shuttle => (
            <div key={shuttle.id} className="bg-white p-6 border border-gray-200 shadow-sm rounded-lg flex flex-col gap-4">
              <div className="flex justify-between items-center">
                <h3 className="font-bold text-gray-800">{shuttle.name}</h3>
                {getStatusBadge(shuttle.status)}
              </div>
              
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600 flex items-center gap-1"><Users size={16} /> Passengers</span>
                  <span className="font-medium text-gray-900">{shuttle.passengers} / {shuttle.capacity}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-in-out" 
                    style={{ width: `${(shuttle.passengers / shuttle.capacity) * 100}%` }}
                  ></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600 flex items-center gap-1"><Route size={16} /> Route Progress</span>
                  <span className="font-medium text-gray-900">{Math.round(shuttle.routeProgress)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-green-500 h-2 rounded-full transition-all duration-500 ease-in-out" 
                    style={{ width: `${shuttle.routeProgress}%` }}
                  ></div>
                </div>
                <div className="text-xs text-gray-500 mt-1 truncate">
                  Current Route: {shuttle.currentRoute}
                </div>
              </div>

              <div className="pt-2 border-t border-gray-100 flex justify-between items-center">
                {getNetworkBadge(shuttle.network)}
                <div className="text-xs text-gray-500">
                  {shuttle.distance.toFixed(1)} km traveled
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Charts section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white p-6 border border-gray-200 shadow-sm rounded-lg flex flex-col">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Passenger Activity</h2>
          <div className="h-64 flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={passengerData} margin={{ top: 5, right: 20, left: -20, bottom: 5 }}>
                <defs>
                  <linearGradient id="colorPassengers" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                <Tooltip 
                  contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Area type="monotone" dataKey="passengers" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorPassengers)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        
        <div className="bg-white p-6 border border-gray-200 shadow-sm rounded-lg flex flex-col">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Trip Count (Today)</h2>
          <div className="h-64 flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tripData} margin={{ top: 5, right: 20, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                <Tooltip 
                  contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  cursor={{ fill: '#f3f4f6' }}
                />
                <Bar dataKey="trips" fill="#1e3a8a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Activity section */}
      <div className="bg-white border border-gray-200 shadow-sm rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <h2 className="text-base font-semibold text-gray-900">Recent Activity</h2>
        </div>
        <div className="p-6 max-h-80 overflow-y-auto">
          <div className="space-y-4">
            {activities.slice(0, 8).map(activity => (
              <div key={activity.id} className="flex items-start gap-3">
                <div className={`mt-1 flex-shrink-0 ${getActivityColor(activity.type)}`}>
                  <Circle size={10} className="fill-current" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800">{activity.message}</p>
                </div>
                <div className="text-xs text-gray-500 whitespace-nowrap">
                  {activity.timestamp}
                </div>
              </div>
            ))}
            {activities.length === 0 && (
              <div className="text-center text-sm text-gray-500 py-4">No recent activity</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
