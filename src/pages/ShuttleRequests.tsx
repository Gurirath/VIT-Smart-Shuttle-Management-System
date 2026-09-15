import React, { useState, useEffect } from 'react';
import { MessageSquare, Clock, Bus, Timer, Send, MapPin, AlertCircle } from 'lucide-react';
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer
} from 'recharts';
import { useToast } from '../components/ToastContext';
import { getShuttleRequests, requestShuttle, getDemandChartData, getDemandByStop } from '../services/api';
import type { ShuttleRequest, DemandByStop } from '../types';
import BackendOffline from '../components/BackendOffline';

const STOPS = ['Main Gate', 'Academic Block', 'SJT', 'Library', 'Hostels'];

export default function ShuttleRequests() {
  const { showToast } = useToast();
  
  // State
  const [requests, setRequests] = useState<ShuttleRequest[]>([]);
  const [demandChartData, setDemandChartData] = useState<{time: string, demand: number}[]>([]);
  const [demandByStop, setDemandByStop] = useState<DemandByStop[]>([]);
  const [backendError, setBackendError] = useState<string | null>(null);

  // Form State
  const [studentId, setStudentId] = useState('');
  const [pickupStop, setPickupStop] = useState('');
  const [destinationStop, setDestinationStop] = useState('');
  const [classEndTime, setClassEndTime] = useState('');

  const fetchData = async () => {
    try {
      const [reqs, chartData, stopData] = await Promise.all([
        getShuttleRequests(),
        getDemandChartData(),
        getDemandByStop()
      ]);
      setRequests(reqs);
      setDemandChartData(chartData);
      setDemandByStop(stopData);
    } catch (error) {
      setBackendError(error instanceof Error ? error.message : 'Failed to fetch requests data');
      console.error('Failed to fetch data', error);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId || !pickupStop || !destinationStop || !classEndTime) {
      showToast('Please fill all fields', 'error');
      return;
    }
    if (pickupStop === destinationStop) {
      showToast('Pickup and destination must be different', 'error');
      return;
    }

    try {
      await requestShuttle({ studentId, pickupStop, destinationStop, classEndTime });
      showToast('Shuttle request submitted successfully', 'success');
      setStudentId('');
      setPickupStop('');
      setDestinationStop('');
      setClassEndTime('');
      fetchData();
    } catch (error) {
      showToast('Failed to submit shuttle request', 'error');
    }
  };

  const getStatusColor = (status: ShuttleRequest['status']) => {
    switch (status) {
      case 'FULFILLED':
        return 'bg-green-100 text-green-800';
      case 'ACKNOWLEDGED':
        return 'bg-blue-100 text-blue-800';
      case 'PENDING':
      default:
        return 'bg-amber-100 text-amber-800';
    }
  };

  const totalRequests = requests.length;

  if (backendError) {
    return <BackendOffline error={backendError} onRetry={() => { setBackendError(null); fetchData(); }} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2846]">Shuttle Requests</h1>
          <p className="text-gray-500">Post-Class Shuttle Demand</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Request Form */}
        <div className="lg:col-span-1 bg-white rounded-lg border border-gray-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-[#1a2846] mb-4 flex items-center">
            <Send className="w-5 h-5 mr-2 text-blue-600" />
            Request a Shuttle
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Student ID</label>
              <input
                type="text"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="e.g. VIT21001"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Pickup Stop</label>
              <select
                value={pickupStop}
                onChange={(e) => setPickupStop(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="">Select Stop</option>
                {STOPS.map(stop => (
                  <option key={stop} value={stop}>{stop}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Destination Stop</label>
              <select
                value={destinationStop}
                onChange={(e) => setDestinationStop(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="">Select Stop</option>
                {STOPS.map(stop => (
                  <option key={stop} value={stop}>{stop}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Class End Time</label>
              <input
                type="time"
                value={classEndTime}
                onChange={(e) => setClassEndTime(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              type="submit"
              className="w-full bg-[#1a2846] hover:bg-[#0d1423] text-white font-medium py-2.5 rounded-lg transition-colors flex justify-center items-center"
            >
              REQUEST SHUTTLE
            </button>
          </form>
        </div>

        {/* Stats Grid */}
        <div className="lg:col-span-2 grid grid-cols-2 gap-4">
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex items-center space-x-4">
            <div className="p-3 bg-blue-100 text-blue-600 rounded-lg">
              <MessageSquare className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Total Requests</p>
              <p className="text-2xl font-bold text-[#1a2846]">{totalRequests}</p>
            </div>
          </div>
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex items-center space-x-4">
            <div className="p-3 bg-indigo-100 text-indigo-600 rounded-lg">
              <Clock className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Peak Demand Time</p>
              <p className="text-2xl font-bold text-[#1a2846]">12:00</p>
            </div>
          </div>
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex items-center space-x-4">
            <div className="p-3 bg-green-100 text-green-600 rounded-lg">
              <Bus className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Recommended Shuttles</p>
              <p className="text-2xl font-bold text-[#1a2846]">2</p>
            </div>
          </div>
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex items-center space-x-4">
            <div className="p-3 bg-orange-100 text-orange-600 rounded-lg">
              <Timer className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Avg Wait Time</p>
              <p className="text-2xl font-bold text-[#1a2846]">8 min</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Demand Over Time Chart */}
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <h2 className="text-lg font-semibold text-[#1a2846] mb-4">Demand Over Time</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={demandChartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="demand" stroke="#1a2846" fill="#bfdbfe" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Demand by Stop Chart */}
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <h2 className="text-lg font-semibold text-[#1a2846] mb-4">Demand by Stop</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={demandByStop} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" />
                <YAxis dataKey="stop" type="category" width={100} />
                <Tooltip />
                <Bar dataKey="count" fill="#1a2846" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Shuttle Planning Panel */}
      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
        <h2 className="text-lg font-semibold text-[#1a2846] mb-4 flex items-center">
          <Bus className="w-5 h-5 mr-2 text-indigo-600" />
          Shuttle Planning Recommendation
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="border border-gray-200 rounded-lg p-4">
            <p className="text-sm text-gray-500 mb-1">Current Demand</p>
            <p className="text-xl font-bold text-[#1a2846]">{totalRequests} students</p>
          </div>
          <div className="border border-gray-200 rounded-lg p-4">
            <p className="text-sm text-gray-500 mb-1">Nearest High-Demand Stop</p>
            <p className="text-xl font-bold text-[#1a2846] flex items-center">
              <MapPin className="w-4 h-4 mr-1 text-gray-400" />
              Main Gate
            </p>
          </div>
          <div className="border border-indigo-200 bg-indigo-50 rounded-lg p-4">
            <p className="text-sm text-indigo-600 mb-1 font-medium">Recommended Action</p>
            <p className="text-xl font-bold text-indigo-900">Deploy 2 shuttles</p>
          </div>
        </div>
        <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded-lg flex items-start">
          <AlertCircle className="w-5 h-5 mr-3 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium mb-1">Recommendation Reason:</p>
            <p className="text-sm text-blue-700 mb-2">
              Demand exceeds single-shuttle capacity (30 seats). Recommend deploying 2 shuttles to serve all requests.
            </p>
            <p className="text-xs text-blue-600/70 italic">
              Note: This is a demo calculation using mock data
            </p>
          </div>
        </div>
      </div>

      {/* Recent Requests Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-lg font-semibold text-[#1a2846]">Recent Requests</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white border-b border-gray-200 text-sm text-gray-500 uppercase tracking-wider">
                <th className="px-6 py-3 font-medium">Request ID</th>
                <th className="px-6 py-3 font-medium">Student</th>
                <th className="px-6 py-3 font-medium">Pickup</th>
                <th className="px-6 py-3 font-medium">Destination</th>
                <th className="px-6 py-3 font-medium">Class End</th>
                <th className="px-6 py-3 font-medium">Request Time</th>
                <th className="px-6 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {requests.slice(0, 15).map((request) => (
                <tr key={request.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {request.id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div>{request.studentName}</div>
                    <div className="text-xs text-gray-400">{request.studentId}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {request.pickupStop}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {request.destinationStop}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {request.classEndTime}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(request.requestTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(request.status)}`}>
                      {request.status}
                    </span>
                  </td>
                </tr>
              ))}
              {requests.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                    No shuttle requests found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
