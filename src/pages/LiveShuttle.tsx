import { useState, useEffect } from 'react';
import {
  Bus, Wifi, Radio, MapPin, Navigation, Signal,
  Pause, Play, ChevronDown, Settings, Thermometer
} from 'lucide-react';
import {
  getShuttles,
  toggleNetwork,
  tickSimulation,
  getRouteStops,
  simulateSensorReading
} from '../services/api';
import type { Shuttle, NetworkMode } from '../types';
import { useToast } from '../components/ToastContext';
import BackendOffline from '../components/BackendOffline';

export default function LiveShuttle() {
  const [shuttles, setShuttles] = useState<Shuttle[]>([]);
  const [selectedShuttleId, setSelectedShuttleId] = useState<string | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [isSimControlsOpen, setIsSimControlsOpen] = useState(false);
  
  // Simulation controls state
  const [simSeat, setSimSeat] = useState(1);
  const [simTemp, setSimTemp] = useState(36.5);
  const [simPressure, setSimPressure] = useState<'HIGH' | 'LOW'>('HIGH');
  
  const { addToast } = useToast();

  const routeStops = getRouteStops();

  const loadShuttles = () => {
    getShuttles().then((data) => {
      setShuttles(data);
      if (data.length > 0 && !selectedShuttleId) {
        setSelectedShuttleId(data[0].id);
      }
    }).catch(error => {
      setBackendError(error instanceof Error ? error.message : 'Failed to load shuttles');
    });
  };

  useEffect(() => {
    loadShuttles();
  }, []);

  useEffect(() => {
    if (isPaused) return;
    
    const interval = setInterval(() => {
      tickSimulation().then((data) => {
        setShuttles(data);
      });
    }, 1000);
    
    return () => clearInterval(interval);
  }, [isPaused]);

  const selectedShuttle = shuttles.find(s => s.id === selectedShuttleId);

  const handleNetworkToggle = async (mode: NetworkMode) => {
    if (!selectedShuttleId) return;
    try {
      await toggleNetwork(selectedShuttleId, mode);
      addToast(`Network switched to ${mode}`, 'info');
      // Optimistic update or wait for tick
      setShuttles(prev => prev.map(s => 
        s.id === selectedShuttleId ? { ...s, network: mode } : s
      ));
    } catch (err) {
      addToast('Failed to toggle network', 'error');
    }
  };

  const handleApplySensor = async () => {
    if (!selectedShuttleId) return;
    try {
      const res = await simulateSensorReading(selectedShuttleId, simSeat, simTemp, simPressure);
      addToast(`Sensor applied. Seat status: ${res.detectedStatus}`, 'success');
    } catch (err) {
      addToast('Failed to apply sensor reading', 'error');
    }
  };

  if (backendError) {
    return <BackendOffline error={backendError} onRetry={() => { setBackendError(null); loadShuttles(); }} />;
  }

  if (!selectedShuttle) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">Loading shuttle data...</p>
      </div>
    );
  }

  // Calculate position along path (simplified linear interpolation between stops based on routeProgress 0-100)
  // routeProgress corresponds to the full route. We have 5 stops.
  // We'll map progress (0-100) to segments.
  const getShuttlePosition = () => {
    if (routeStops.length < 2) return { x: 0, y: 0 };
    
    const totalSegments = routeStops.length - 1;
    const progressFraction = selectedShuttle.routeProgress / 100;
    const currentSegmentFloat = progressFraction * totalSegments;
    const currentSegmentIndex = Math.min(Math.floor(currentSegmentFloat), totalSegments - 1);
    
    const segmentProgress = currentSegmentFloat - currentSegmentIndex;
    
    const startStop = routeStops[currentSegmentIndex];
    const endStop = routeStops[currentSegmentIndex + 1];
    
    const x = startStop.x + (endStop.x - startStop.x) * segmentProgress;
    const y = startStop.y + (endStop.y - startStop.y) * segmentProgress;
    
    return { x, y };
  };

  const shuttlePos = getShuttlePosition();

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* 1. Shuttle Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center bg-white p-4 rounded-xl shadow-sm border border-gray-100 gap-4">
        <div className="flex items-center gap-4">
          <div className="bg-navy-50 text-navy-600 p-3 rounded-lg">
            <Bus className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{selectedShuttle.name}</h1>
            <div className="flex gap-2 mt-2">
              {shuttles.map(shuttle => (
                <button
                  key={shuttle.id}
                  onClick={() => setSelectedShuttleId(shuttle.id)}
                  className={`px-3 py-1 text-sm font-medium rounded-full transition-colors ${
                    selectedShuttleId === shuttle.id 
                      ? 'bg-navy-600 text-white' 
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {shuttle.name}
                </button>
              ))}
            </div>
          </div>
        </div>
        
        <button
          onClick={() => setIsPaused(!isPaused)}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
            isPaused 
              ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
              : 'bg-green-100 text-green-700 hover:bg-green-200'
          }`}
        >
          {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
          {isPaused ? 'Resume Updates' : 'Pause Updates'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* 2. Main info panel (~60%) */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-6 border-b border-gray-100">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Vehicle Status</h2>
                  <p className="text-sm text-gray-500 font-mono mt-1">ID: {selectedShuttle.id}</p>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide ${
                  selectedShuttle.status === 'RUNNING' ? 'bg-green-100 text-green-700' :
                  selectedShuttle.status === 'IDLE' ? 'bg-gray-100 text-gray-700' :
                  'bg-red-100 text-red-700'
                }`}>
                  {selectedShuttle.status}
                </span>
              </div>

              {/* Passengers */}
              <div className="mb-6">
                <div className="flex justify-between text-sm mb-2">
                  <span className="font-medium text-gray-700">
                    {selectedShuttle.passengers} / {selectedShuttle.capacity} passengers
                  </span>
                  <span className="text-gray-500">
                    {selectedShuttle.capacity - selectedShuttle.passengers} seats available
                  </span>
                </div>
                <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-navy-600 rounded-full transition-all duration-500"
                    style={{ width: `${(selectedShuttle.passengers / selectedShuttle.capacity) * 100}%` }}
                  />
                </div>
              </div>

              {/* Grid Details */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="flex items-center gap-2 text-gray-500 mb-1">
                    <MapPin className="w-4 h-4" />
                    <span className="text-xs font-medium uppercase">Coordinates</span>
                  </div>
                  <p className="font-mono text-sm text-gray-900">
                    {selectedShuttle.latitude.toFixed(6)}, {selectedShuttle.longitude.toFixed(6)}
                  </p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="flex items-center gap-2 text-gray-500 mb-1">
                    <Navigation className="w-4 h-4" />
                    <span className="text-xs font-medium uppercase">Current Route</span>
                  </div>
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {selectedShuttle.currentRoute}
                  </p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <div className="flex items-center gap-2 text-gray-500 mb-1">
                    <Bus className="w-4 h-4" />
                    <span className="text-xs font-medium uppercase">Trip Info</span>
                  </div>
                  <p className="font-mono text-xs text-gray-900 truncate mb-1">
                    ID: {selectedShuttle.currentTrip}
                  </p>
                  <p className="text-sm font-medium text-gray-900">
                    {selectedShuttle.distance} km • ₹{selectedShuttle.estimatedFare.toFixed(2)}
                  </p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg flex flex-col justify-center">
                  <div className="text-xs font-medium uppercase text-gray-500 mb-2">Route Progress</div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-green-500 transition-all duration-500"
                        style={{ width: `${selectedShuttle.routeProgress}%` }}
                      />
                    </div>
                    <span className="text-sm font-bold text-gray-700">
                      {Math.round(selectedShuttle.routeProgress)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Network Status & Controls */}
              <div className="border-t border-gray-100 pt-6">
                <h3 className="text-sm font-bold text-gray-900 mb-4 uppercase tracking-wider">Network Systems</h3>
                
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="flex flex-col items-center justify-center p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <Wifi className={`w-5 h-5 mb-2 ${selectedShuttle.network === 'WIFI_MQTT' ? 'text-green-500' : 'text-red-500'}`} />
                    <span className="text-xs font-medium text-gray-500 mb-1">WiFi</span>
                    <span className={`text-xs font-bold ${selectedShuttle.network === 'WIFI_MQTT' ? 'text-green-600' : 'text-red-600'}`}>
                      {selectedShuttle.network === 'WIFI_MQTT' ? 'ONLINE' : 'OFFLINE'}
                    </span>
                  </div>
                  <div className="flex flex-col items-center justify-center p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <Radio className={`w-5 h-5 mb-2 ${selectedShuttle.network === 'WIFI_MQTT' ? 'text-green-500' : 'text-red-500'}`} />
                    <span className="text-xs font-medium text-gray-500 mb-1">MQTT</span>
                    <span className={`text-xs font-bold ${selectedShuttle.network === 'WIFI_MQTT' ? 'text-green-600' : 'text-red-600'}`}>
                      {selectedShuttle.network === 'WIFI_MQTT' ? 'ONLINE' : 'OFFLINE'}
                    </span>
                  </div>
                  <div className="flex flex-col items-center justify-center p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <Signal className={`w-5 h-5 mb-2 ${selectedShuttle.network === 'GSM_FALLBACK' ? 'text-amber-500' : 'text-gray-400'}`} />
                    <span className="text-xs font-medium text-gray-500 mb-1">GSM FALLBACK</span>
                    <span className={`text-xs font-bold ${selectedShuttle.network === 'GSM_FALLBACK' ? 'text-amber-600' : 'text-gray-500'}`}>
                      {selectedShuttle.network === 'GSM_FALLBACK' ? 'ACTIVE' : 'STANDBY'}
                    </span>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button 
                    onClick={() => handleNetworkToggle('WIFI_MQTT')}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium border transition-colors ${
                      selectedShuttle.network === 'WIFI_MQTT' 
                        ? 'bg-navy-50 border-navy-200 text-navy-700 ring-1 ring-navy-600'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Primary (WiFi)
                  </button>
                  <button 
                    onClick={() => handleNetworkToggle('GSM_FALLBACK')}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium border transition-colors ${
                      selectedShuttle.network === 'GSM_FALLBACK' 
                        ? 'bg-amber-50 border-amber-200 text-amber-700 ring-1 ring-amber-500'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Fallback (GSM)
                  </button>
                  <button 
                    onClick={() => handleNetworkToggle('OFFLINE')}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium border transition-colors ${
                      selectedShuttle.network === 'OFFLINE' 
                        ? 'bg-red-50 border-red-200 text-red-700 ring-1 ring-red-500'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Force Offline
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 4. Campus Route Visualization (~40%) */}
        <div className="lg:col-span-5 bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex flex-col">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Live Map</h2>
          
          <div className="relative w-full aspect-[4/3] bg-gray-50 rounded-xl overflow-hidden border border-gray-200 flex-1 flex items-center justify-center p-4">
            <svg viewBox="0 0 700 450" className="w-full h-full drop-shadow-sm">
              {/* Path connecting stops */}
              <path 
                d={`M ${routeStops.map(s => `${s.x} ${s.y}`).join(' L ')}`} 
                fill="none" 
                stroke="#cbd5e1" 
                strokeWidth="6" 
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray="12 12"
              />
              
              {/* Stops */}
              {routeStops.map((stop) => (
                <g key={stop.id}>
                  <circle 
                    cx={stop.x} 
                    cy={stop.y} 
                    r="8" 
                    fill="#1e293b" 
                    stroke="#ffffff" 
                    strokeWidth="3" 
                  />
                  <rect
                    x={stop.x - 45}
                    y={stop.y + 15}
                    width="90"
                    height="24"
                    rx="12"
                    fill="#ffffff"
                    stroke="#e2e8f0"
                  />
                  <text 
                    x={stop.x} 
                    y={stop.y + 31} 
                    textAnchor="middle" 
                    fontSize="11" 
                    fontWeight="600"
                    fill="#475569"
                  >
                    {stop.name}
                  </text>
                </g>
              ))}

              {/* Active Shuttle Marker */}
              <g 
                className="transition-all duration-1000 ease-linear"
                style={{ transform: `translate(${shuttlePos.x}px, ${shuttlePos.y}px)` }}
              >
                <circle cx="0" cy="0" r="14" fill="#22c55e" className="animate-ping opacity-20" />
                <circle cx="0" cy="0" r="14" fill="#ffffff" stroke="#22c55e" strokeWidth="3" />
                <circle cx="0" cy="0" r="6" fill="#22c55e" />
                <rect x="-30" y="-35" width="60" height="20" rx="10" fill="#22c55e" />
                <text x="0" y="-21" textAnchor="middle" fontSize="10" fontWeight="bold" fill="#ffffff">
                  {selectedShuttle.name.split('-').pop()}
                </text>
              </g>
            </svg>
          </div>
        </div>
      </div>

      {/* 5. Simulation Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <button 
          onClick={() => setIsSimControlsOpen(!isSimControlsOpen)}
          className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors border-b border-gray-100"
        >
          <div className="flex items-center gap-2 text-navy-700">
            <Settings className="w-5 h-5" />
            <span className="font-bold">Hardware Simulation Controls</span>
          </div>
          <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${isSimControlsOpen ? 'rotate-180' : ''}`} />
        </button>
        
        {isSimControlsOpen && (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 bg-gray-50">
            <div>
              <label className="block text-xs font-bold text-gray-700 uppercase mb-2">Seat Number</label>
              <select 
                value={simSeat}
                onChange={(e) => setSimSeat(Number(e.target.value))}
                className="w-full border-gray-300 rounded-lg shadow-sm focus:border-navy-500 focus:ring-navy-500 p-2 border"
              >
                {Array.from({ length: 30 }, (_, i) => i + 1).map(num => (
                  <option key={num} value={num}>Seat {num}</option>
                ))}
              </select>
            </div>
            
            <div className="lg:col-span-2">
              <label className="block text-xs font-bold text-gray-700 uppercase mb-2 flex items-center gap-1">
                <Thermometer className="w-3 h-3" /> Temperature ({simTemp.toFixed(1)}°C)
              </label>
              <div className="flex items-center gap-4">
                <input 
                  type="range" 
                  min="25.0" 
                  max="40.0" 
                  step="0.1" 
                  value={simTemp}
                  onChange={(e) => setSimTemp(parseFloat(e.target.value))}
                  className="w-full accent-navy-600"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-xs font-bold text-gray-700 uppercase mb-2">Pressure Pad</label>
              <select 
                value={simPressure}
                onChange={(e) => setSimPressure(e.target.value as 'HIGH' | 'LOW')}
                className="w-full border-gray-300 rounded-lg shadow-sm focus:border-navy-500 focus:ring-navy-500 p-2 border"
              >
                <option value="HIGH">HIGH (Triggered)</option>
                <option value="LOW">LOW (Empty)</option>
              </select>
            </div>
            
            <div className="flex items-end">
              <button 
                onClick={handleApplySensor}
                className="w-full bg-navy-600 hover:bg-navy-700 text-white font-medium py-2 px-4 rounded-lg transition-colors shadow-sm"
              >
                Apply Reading
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
