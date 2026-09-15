import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Bus, LayoutDashboard, Radio, Grid3X3, Users, MessageSquare, Receipt, FileText } from 'lucide-react';

const MainLayout: React.FC = () => {
  const location = useLocation();

  const getPageTitle = (pathname: string) => {
    switch (pathname) {
      case '/dashboard': return 'Dashboard';
      case '/live-shuttle': return 'Live Shuttle';
      case '/seats': return 'Seat Allocation';
      case '/students': return 'Students';
      case '/requests': return 'Shuttle Requests';
      case '/trips': return 'Trips & Billing';
      case '/vehicle-logs': return 'Vehicle Logs';
      default: return 'VIT Smart Shuttle';
    }
  };

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/live-shuttle', label: 'Live Shuttle', icon: Radio },
    { path: '/seats', label: 'Seat Allocation', icon: Grid3X3 },
    { path: '/students', label: 'Students', icon: Users },
    { path: '/requests', label: 'Shuttle Requests', icon: MessageSquare },
    { path: '/trips', label: 'Trips & Billing', icon: Receipt },
    { path: '/vehicle-logs', label: 'Vehicle Logs', icon: FileText },
  ];

  return (
    <div className="flex h-screen bg-gray-50 font-sans text-gray-900">
      {/* Sidebar */}
      <aside className="w-64 fixed inset-y-0 left-0 bg-[#0d1423] text-gray-300 flex flex-col z-20">
        <div className="flex items-center gap-3 p-6">
          <Bus className="w-8 h-8 text-blue-400" />
          <span className="font-bold text-white tracking-wide">VIT SMART SHUTTLE</span>
        </div>
        
        <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors duration-200 ${
                  isActive
                    ? 'bg-[#1a2846] text-white'
                    : 'hover:bg-[#1a2846] hover:text-white'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              <span className="font-medium text-sm">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center gap-2 px-4 py-2 bg-[#1a2846] rounded-lg">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <span className="text-sm font-medium text-white">System Online</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-64 flex flex-col min-h-screen">
        {/* Top Bar */}
        <header className="bg-white border-b border-gray-200 px-8 py-4 sticky top-0 z-10 shadow-sm">
          <h1 className="text-2xl font-bold text-gray-800">
            {getPageTitle(location.pathname)}
          </h1>
        </header>

        {/* Content Area */}
        <div className="flex-1 p-6 overflow-y-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default MainLayout;
