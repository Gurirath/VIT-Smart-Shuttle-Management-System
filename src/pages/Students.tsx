import React, { useState, useEffect, useMemo } from 'react';
import { Search, User, Filter } from 'lucide-react';
import { getStudents } from '../services/api';
import type { Student } from '../types';
import Modal from '../components/Modal';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';
import BackendOffline from '../components/BackendOffline';

const Students: React.FC = () => {
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState<string | null>(null);
  
  // Filters state
  const [searchTerm, setSearchTerm] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('All');
  const [genderFilter, setGenderFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [shuttleFilter, setShuttleFilter] = useState('All');

  // Modal state
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchStudents = async () => {
    setLoading(true);
    setBackendError(null);
    try {
      const data = await getStudents();
      setStudents(data);
    } catch (error) {
      setBackendError(error instanceof Error ? error.message : 'Failed to fetch students');
      console.error('Error fetching students:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStudents();
  }, []);

  const filteredStudents = useMemo(() => {
    return students.filter(student => {
      const matchesSearch = 
        student.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
        student.registerNumber.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesDepartment = departmentFilter === 'All' || student.department === departmentFilter;
      const matchesGender = genderFilter === 'All' || student.gender === genderFilter;
      const matchesStatus = statusFilter === 'All' || student.status === statusFilter;
      const matchesShuttle = shuttleFilter === 'All' || 
        (shuttleFilter === 'VIT-SHUTTLE-01' && student.currentShuttle === 'VIT-SHUTTLE-01') ||
        (shuttleFilter === 'VIT-SHUTTLE-02' && student.currentShuttle === 'VIT-SHUTTLE-02');

      return matchesSearch && matchesDepartment && matchesGender && matchesStatus && matchesShuttle;
    });
  }, [students, searchTerm, departmentFilter, genderFilter, statusFilter, shuttleFilter]);

  const handleRowClick = (student: Student) => {
    setSelectedStudent(student);
    setIsModalOpen(true);
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'ON_SHUTTLE':
        return 'bg-green-100 text-green-800';
      case 'ON_CAMPUS':
        return 'bg-blue-100 text-blue-800';
      case 'OFF_CAMPUS':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getPaymentBadgeClass = (status: string) => {
    switch (status) {
      case 'PROCESSED':
        return 'bg-green-100 text-green-800';
      case 'PENDING':
        return 'bg-amber-100 text-amber-800';
      case 'FAILED':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (backendError) {
    return <BackendOffline error={backendError} onRetry={fetchStudents} />;
  }

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Students</h1>
        <p className="text-gray-600 mt-1">Student management and tracking</p>
      </div>

      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm mb-6">
        <div className="flex flex-col md:flex-row md:items-center gap-4 mb-4">
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              placeholder="Search by name or register number..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border py-2"
            />
          </div>
          <div className="flex flex-wrap gap-4 items-center">
            <div className="flex items-center text-sm text-gray-500">
              <Filter className="w-4 h-4 mr-2" /> Filters:
            </div>
            <select
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border py-2 pl-3 pr-8"
            >
              <option value="All">All Depts</option>
              <option value="CSE">CSE</option>
              <option value="ECE">ECE</option>
              <option value="MECH">MECH</option>
              <option value="IT">IT</option>
              <option value="BIO">BIO</option>
            </select>
            
            <select
              value={genderFilter}
              onChange={(e) => setGenderFilter(e.target.value)}
              className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border py-2 pl-3 pr-8"
            >
              <option value="All">All Genders</option>
              <option value="Male">Male</option>
              <option value="Female">Female</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border py-2 pl-3 pr-8"
            >
              <option value="All">All Statuses</option>
              <option value="ON_SHUTTLE">ON_SHUTTLE</option>
              <option value="ON_CAMPUS">ON_CAMPUS</option>
              <option value="OFF_CAMPUS">OFF_CAMPUS</option>
            </select>

            <select
              value={shuttleFilter}
              onChange={(e) => setShuttleFilter(e.target.value)}
              className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border py-2 pl-3 pr-8"
            >
              <option value="All">All Shuttles</option>
              <option value="VIT-SHUTTLE-01">VIT-SHUTTLE-01</option>
              <option value="VIT-SHUTTLE-02">VIT-SHUTTLE-02</option>
            </select>
          </div>
        </div>
        <div className="text-sm text-gray-500">
          Showing {filteredStudents.length} of {students.length} students
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        {filteredStudents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Register Number
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Gender
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Department
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Current Status
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Current Shuttle
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Trips Today
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Payment Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredStudents.map((student) => (
                  <tr 
                    key={student.id} 
                    onClick={() => handleRowClick(student)}
                    className="hover:bg-blue-50 cursor-pointer even:bg-gray-50 transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-navy-900">
                      {student.registerNumber}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {student.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center">
                        <User className="h-4 w-4 mr-1 text-gray-400" />
                        {student.gender}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {student.department}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadgeClass(student.status)}`}>
                        {student.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {student.currentShuttle || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {student.tripsToday}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getPaymentBadgeClass(student.paymentStatus)}`}>
                        {student.paymentStatus}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState 
            icon={User}
            title="No students found"
            description="We couldn't find any students matching your current filters."
          />
        )}
      </div>

      <Modal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        title="Student Details"
      >
        {selectedStudent && (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-3 border-b pb-2">Personal Information</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">Register Number</div>
                  <div className="font-medium text-gray-900">{selectedStudent.registerNumber}</div>
                </div>
                <div>
                  <div className="text-gray-500">Name</div>
                  <div className="font-medium text-gray-900">{selectedStudent.name}</div>
                </div>
                <div>
                  <div className="text-gray-500">Gender</div>
                  <div className="font-medium text-gray-900">{selectedStudent.gender}</div>
                </div>
                <div>
                  <div className="text-gray-500">Department</div>
                  <div className="font-medium text-gray-900">{selectedStudent.department}</div>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-3 border-b pb-2">Current Status</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">Status</div>
                  <div className="mt-1">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadgeClass(selectedStudent.status)}`}>
                      {selectedStudent.status.replace('_', ' ')}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Current Shuttle</div>
                  <div className="font-medium text-gray-900">{selectedStudent.currentShuttle || 'Not on shuttle'}</div>
                </div>
                <div>
                  <div className="text-gray-500">Current Seat</div>
                  <div className="font-medium text-gray-900">{selectedStudent.currentSeat ?? '-'}</div>
                </div>
                <div>
                  <div className="text-gray-500">Trip ID</div>
                  <div className="font-medium text-gray-900 text-xs mt-1">{selectedStudent.tripId || '-'}</div>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-3 border-b pb-2">Today's Activity</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">Trips Today</div>
                  <div className="font-medium text-gray-900">{selectedStudent.tripsToday}</div>
                </div>
                <div>
                  <div className="text-gray-500">Total Distance</div>
                  <div className="font-medium text-gray-900">{selectedStudent.totalDistance.toFixed(2)} km</div>
                </div>
                <div>
                  <div className="text-gray-500">Total Fare</div>
                  <div className="font-medium text-gray-900">₹{selectedStudent.totalFare.toFixed(2)}</div>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-3 border-b pb-2">Payment</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">Payment Account</div>
                  <div className="font-medium text-gray-900">Fee Account</div>
                </div>
                <div>
                  <div className="text-gray-500">Payment Status</div>
                  <div className="mt-1">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getPaymentBadgeClass(selectedStudent.paymentStatus)}`}>
                      {selectedStudent.paymentStatus}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Students;
