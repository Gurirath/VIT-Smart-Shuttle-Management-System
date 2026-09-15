import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './components/ToastContext';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import LiveShuttle from './pages/LiveShuttle';
import SeatAllocation from './pages/SeatAllocation';
import Students from './pages/Students';
import ShuttleRequests from './pages/ShuttleRequests';
import TripsAndBilling from './pages/TripsAndBilling';
import VehicleLogs from './pages/VehicleLogs';

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route element={<MainLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/live-shuttle" element={<LiveShuttle />} />
            <Route path="/seats" element={<SeatAllocation />} />
            <Route path="/students" element={<Students />} />
            <Route path="/requests" element={<ShuttleRequests />} />
            <Route path="/trips" element={<TripsAndBilling />} />
            <Route path="/vehicle-logs" element={<VehicleLogs />} />
          </Route>
        </Routes>
      </ToastProvider>
    </BrowserRouter>
  );
}
