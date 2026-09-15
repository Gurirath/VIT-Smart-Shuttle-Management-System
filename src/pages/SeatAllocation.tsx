import React, { useState, useEffect } from 'react';
import { 
  Grid3X3, 
  Users, 
  Package, 
  CheckCircle, 
  User, 
  Armchair, 
  Thermometer, 
  Activity, 
  Clock, 
  Navigation
} from 'lucide-react';
import type { Seat, Shuttle, SeatStatus } from '../types';
import { getSeats, getShuttles, getSeat } from '../services/api';
import Modal from '../components/Modal';
import { useToast } from '../components/ToastContext';
import BackendOffline from '../components/BackendOffline';

const SeatAllocation: React.FC = () => {
  const [shuttles, setShuttles] = useState<Shuttle[]>([]);
  const [selectedShuttleId, setSelectedShuttleId] = useState<string>('');
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selectedSeat, setSelectedSeat] = useState<Seat | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const { showToast } = useToast();

  const fetchShuttles = async () => {
    try {
      const data = await getShuttles();
      setShuttles(data);
      if (data.length > 0 && !selectedShuttleId) {
        setSelectedShuttleId(data[0].id);
      }
    } catch (error) {
      setBackendError(error instanceof Error ? error.message : 'Failed to fetch shuttles');
      showToast('Failed to fetch shuttles', 'error');
    }
  };

  useEffect(() => {
    fetchShuttles();
  }, [showToast]);

  useEffect(() => {
    if (!selectedShuttleId) return;
    
    const fetchSeats = async () => {
      try {
        const data = await getSeats(selectedShuttleId);
        setSeats(data);
        
        // Update selected seat if modal is open
        setSelectedSeat(prev => {
          if (!prev) return prev;
          const updated = data.find(s => s.id === prev.id);
          return updated || prev;
        });
      } catch (error) {
        setBackendError(error instanceof Error ? error.message : 'Failed to fetch seats');
        console.error('Failed to fetch seats', error);
      }
    };
    
    fetchSeats();
    const interval = setInterval(fetchSeats, 1000);
    return () => clearInterval(interval);
  }, [selectedShuttleId]);

  const handleSeatClick = async (seatNum: number) => {
    try {
      if (!selectedShuttleId) return;
      const seat = await getSeat(selectedShuttleId, seatNum);
      if (seat) {
        setSelectedSeat(seat);
        setIsModalOpen(true);
      } else {
        // Fallback to local state if individual fetch fails
        const localSeat = seats.find(s => s.number === seatNum);
        if (localSeat) {
          setSelectedSeat(localSeat);
          setIsModalOpen(true);
        }
      }
    } catch (error) {
      showToast('Failed to get seat details', 'error');
    }
  };

  const getSeatColor = (status: SeatStatus) => {
    switch (status) {
      case 'AVAILABLE':
        return 'bg-emerald-50 border-emerald-200 hover:bg-emerald-100';
      case 'OCCUPIED':
        return 'bg-red-50 border-red-300 hover:bg-red-100';
      case 'OBJECT':
        return 'bg-amber-50 border-amber-300 hover:bg-amber-100';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const getSeatTextColor = (status: SeatStatus) => {
    switch (status) {
      case 'AVAILABLE': return 'text-emerald-700';
      case 'OCCUPIED': return 'text-red-700';
      case 'OBJECT': return 'text-amber-700';
      default: return 'text-gray-700';
    }
  };

  const occupiedCount = seats.filter(s => s.status === 'OCCUPIED').length;
  const objectCount = seats.filter(s => s.status === 'OBJECT').length;
  const availableCount = seats.filter(s => s.status === 'AVAILABLE').length;

  // Render a single seat
  const renderSeat = (seatNum: number) => {
    const seat = seats.find(s => s.number === seatNum);
    if (!seat) return <div className="w-20 h-24 invisible"></div>; // Placeholder if missing

    return (
      <div
        key={`seat-${seatNum}`}
        onClick={() => handleSeatClick(seatNum)}
        className={`w-20 h-24 border-2 rounded-xl flex flex-col items-center justify-center p-2 cursor-pointer transition-all duration-200 hover:shadow-md shadow-sm relative ${getSeatColor(seat.status)}`}
      >
        <span className={`text-xl font-bold mb-1 ${getSeatTextColor(seat.status)}`}>
          {String(seat.number).padStart(2, '0')}
        </span>
        
        {seat.status === 'OCCUPIED' && (
          <div className="flex flex-col items-center">
            <User className="w-5 h-5 text-red-500 mb-1" />
            <span className="text-[10px] font-semibold text-red-700 text-center uppercase tracking-tight line-clamp-1">{seat.studentId}</span>
          </div>
        )}
        
        {seat.status === 'OBJECT' && (
          <div className="flex flex-col items-center">
            <Package className="w-5 h-5 text-amber-500 mb-1" />
            <span className="text-[10px] font-semibold text-amber-700 text-center uppercase">Object</span>
          </div>
        )}
        
        {seat.status === 'AVAILABLE' && (
          <div className="flex flex-col items-center">
            <CheckCircle className="w-5 h-5 text-emerald-500 mb-1 opacity-50" />
            <span className="text-[10px] font-semibold text-emerald-700 text-center uppercase">Empty</span>
          </div>
        )}
      </div>
    );
  };

  if (backendError) {
    return <BackendOffline error={backendError} onRetry={() => { setBackendError(null); fetchShuttles(); }} />;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Armchair className="w-8 h-8 text-indigo-600" />
            Seat Allocation
          </h1>
          <p className="text-gray-500 mt-1">Real-time monitoring of seating and object detection</p>
        </div>
        
        <div className="flex items-center gap-3 bg-white p-2 rounded-lg border border-gray-200 shadow-sm">
          <label htmlFor="shuttle-select" className="text-sm font-medium text-gray-700 ml-2">
            Shuttle:
          </label>
          <select
            id="shuttle-select"
            value={selectedShuttleId}
            onChange={(e) => setSelectedShuttleId(e.target.value)}
            className="border-gray-300 rounded-md text-gray-700 font-medium focus:ring-indigo-500 focus:border-indigo-500 py-1.5 pl-3 pr-8"
          >
            {shuttles.map((shuttle) => (
              <option key={shuttle.id} value={shuttle.id}>
                {shuttle.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex items-center gap-4">
          <div className="bg-indigo-50 p-3 rounded-lg text-indigo-600">
            <Grid3X3 className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Total Seats</p>
            <p className="text-2xl font-bold text-gray-900">30</p>
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex items-center gap-4">
          <div className="bg-red-50 p-3 rounded-lg text-red-600">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Occupied</p>
            <p className="text-2xl font-bold text-gray-900">{occupiedCount}</p>
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex items-center gap-4">
          <div className="bg-amber-50 p-3 rounded-lg text-amber-600">
            <Package className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Non-Human Objects</p>
            <p className="text-2xl font-bold text-gray-900">{objectCount}</p>
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex items-center gap-4">
          <div className="bg-emerald-50 p-3 rounded-lg text-emerald-600">
            <CheckCircle className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium">Available</p>
            <p className="text-2xl font-bold text-gray-900">{availableCount}</p>
          </div>
        </div>
      </div>

      {/* Main Grid Area */}
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 flex flex-col items-center">
        {/* Shuttle Body Container */}
        <div className="bg-slate-50 border-4 border-slate-300 rounded-[3rem] p-6 sm:p-10 max-w-3xl w-full shadow-inner relative overflow-hidden">
          
          {/* Driver Area */}
          <div className="bg-slate-200 rounded-2xl p-6 mb-10 flex justify-between items-center relative border border-slate-300 shadow-sm">
            <div className="w-16 h-16 rounded-full border-4 border-slate-400 flex items-center justify-center bg-slate-100">
              <div className="w-8 h-8 rounded-full border-2 border-slate-400 flex items-center justify-center relative">
                <div className="w-full h-0.5 bg-slate-400 absolute"></div>
                <div className="w-0.5 h-full bg-slate-400 absolute"></div>
              </div>
            </div>
            
            <div className="text-center font-bold text-slate-400 tracking-widest text-xl">
              FRONT
            </div>
            
            {/* Door indicator */}
            <div className="absolute right-[-2.5rem] top-1/2 -translate-y-1/2 w-10 h-24 bg-white/60 border border-slate-300 flex items-center justify-center rounded-l shadow-sm">
               <span className="rotate-90 text-[10px] font-bold text-slate-500 tracking-wider">DOOR</span>
            </div>
          </div>

          {/* Seat Grid rows */}
          <div className="space-y-4">
            {/* Rows 1-7 */}
            {[0, 1, 2, 3, 4, 5, 6].map(rowIdx => (
              <div key={`row-${rowIdx}`} className="flex justify-between items-center">
                <div className="flex gap-4">
                  {renderSeat(rowIdx * 4 + 1)}
                  {renderSeat(rowIdx * 4 + 2)}
                </div>
                {/* Center Aisle */}
                <div className="w-16 h-full flex items-center justify-center opacity-30">
                  <div className="w-1 h-full bg-slate-300 rounded-full"></div>
                </div>
                <div className="flex gap-4">
                  {renderSeat(rowIdx * 4 + 3)}
                  {renderSeat(rowIdx * 4 + 4)}
                </div>
              </div>
            ))}
            
            {/* Row 8 (Back row left) */}
            <div className="flex justify-between items-center mt-6">
              <div className="flex gap-4">
                {renderSeat(29)}
                {renderSeat(30)}
              </div>
              <div className="flex-1 flex justify-end">
                {/* Back door indicator */}
                 <div className="w-10 h-16 bg-white/60 border border-slate-300 flex items-center justify-center rounded-l shadow-sm -mr-6 sm:-mr-10">
                   <span className="rotate-90 text-[10px] font-bold text-slate-500 tracking-wider whitespace-nowrap">EXIT</span>
                 </div>
              </div>
            </div>
          </div>
          
        </div>

        {/* Legend */}
        <div className="mt-8 flex flex-wrap justify-center gap-6">
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-emerald-500"></span>
            <span className="text-sm font-medium text-gray-700">Available</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-red-500"></span>
            <span className="text-sm font-medium text-gray-700">Occupied (Student)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-amber-500"></span>
            <span className="text-sm font-medium text-gray-700">Non-Human Object</span>
          </div>
        </div>
      </div>

      {/* Seat Detail Modal */}
      <Modal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        title={`Seat ${selectedSeat?.number.toString().padStart(2, '0') || ''} Details`}
      >
        {selectedSeat && (
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b pb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Current Status</h3>
                <p className="text-sm text-gray-500">Real-time sensor data</p>
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-bold border uppercase ${getSeatColor(selectedSeat.status)} ${getSeatTextColor(selectedSeat.status)}`}>
                {selectedSeat.status.replace('_', ' ')}
              </span>
            </div>

            {selectedSeat.status === 'OCCUPIED' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 bg-slate-50 p-4 rounded-lg border border-slate-200 flex items-start gap-3">
                  <User className="w-10 h-10 text-indigo-500 bg-indigo-100 p-2 rounded-full" />
                  <div>
                    <p className="text-sm text-gray-500 font-medium">Passenger</p>
                    <p className="text-lg font-bold text-gray-900">{selectedSeat.studentName}</p>
                    <p className="text-sm text-indigo-600 font-medium">{selectedSeat.studentId}</p>
                  </div>
                </div>
                
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <p className="text-xs text-gray-500 font-medium mb-1">Gender</p>
                  <p className="font-semibold text-gray-800">{selectedSeat.gender}</p>
                </div>
                
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <p className="text-xs text-gray-500 font-medium mb-1">Entry Time</p>
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-gray-500" />
                    <p className="font-semibold text-gray-800">
                      {selectedSeat.entryTime ? new Date(selectedSeat.entryTime).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'N/A'}
                    </p>
                  </div>
                </div>
                
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <p className="text-xs text-gray-500 font-medium mb-1">Pressure Sensor</p>
                  <div className="flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-indigo-500" />
                    <p className="font-semibold text-gray-800">{selectedSeat.pressure}</p>
                  </div>
                </div>
                
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <p className="text-xs text-gray-500 font-medium mb-1">Temperature</p>
                  <div className="flex items-center gap-1.5">
                    <Thermometer className="w-3.5 h-3.5 text-red-500" />
                    <p className="font-semibold text-gray-800">{selectedSeat.temperature}°C</p>
                  </div>
                </div>
                
                <div className="col-span-2 bg-slate-50 p-3 rounded-lg border border-slate-200 flex justify-between items-center">
                   <div>
                     <p className="text-xs text-gray-500 font-medium mb-1">Trip ID</p>
                     <div className="flex items-center gap-1.5">
                       <Navigation className="w-3.5 h-3.5 text-gray-500" />
                       <p className="font-semibold text-gray-800 text-sm">{selectedSeat.tripId}</p>
                     </div>
                   </div>
                </div>
              </div>
            )}

            {selectedSeat.status === 'OBJECT' && (
              <div className="space-y-4">
                <div className="bg-amber-50 border border-amber-200 p-4 rounded-lg flex gap-3">
                  <Package className="w-6 h-6 text-amber-600 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-amber-900">Non-human object detected - not a student</h4>
                    <p className="text-sm text-amber-700 mt-1">
                      The pressure sensor is triggered, but the surface temperature is outside the human
                      band (34.0-42.0&nbsp;&deg;C). This indicates a non-human object such as a bag or parcel
                      occupying the seat.
                    </p>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <p className="text-xs text-gray-500 font-medium mb-1">Pressure Sensor</p>
                    <div className="flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 text-indigo-500" />
                      <p className="font-semibold text-gray-800">{selectedSeat.pressure} (detected)</p>
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <p className="text-xs text-gray-500 font-medium mb-1">Temperature</p>
                    <div className="flex items-center gap-1.5">
                      <Thermometer className="w-3.5 h-3.5 text-blue-500" />
                      <p className="font-semibold text-gray-800">{selectedSeat.temperature}°C</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {selectedSeat.status === 'AVAILABLE' && (
              <div className="flex flex-col items-center justify-center p-8 bg-emerald-50 rounded-xl border border-emerald-100 text-center">
                <CheckCircle className="w-12 h-12 text-emerald-400 mb-3" />
                <h4 className="text-lg font-semibold text-emerald-900">Seat is empty and available</h4>
                <p className="text-sm text-emerald-700 mt-2 max-w-xs">
                  Sensors indicate normal ambient temperature and low pressure on this seat.
                </p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default SeatAllocation;
