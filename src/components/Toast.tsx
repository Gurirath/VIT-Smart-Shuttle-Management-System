import React from 'react';
import { CheckCircle, XCircle, Info, AlertTriangle, X } from 'lucide-react';
import type { ToastMessage } from './ToastContext';

interface ToastProps {
  toasts: ToastMessage[];
  removeToast: (id: string) => void;
}

const Toast: React.FC<ToastProps> = ({ toasts, removeToast }) => {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => {
        const getIcon = () => {
          switch (toast.type) {
            case 'success': return <CheckCircle className="w-5 h-5 text-green-500" />;
            case 'error': return <XCircle className="w-5 h-5 text-red-500" />;
            case 'info': return <Info className="w-5 h-5 text-blue-500" />;
            case 'warning': return <AlertTriangle className="w-5 h-5 text-amber-500" />;
          }
        };

        const getBgColor = () => {
          switch (toast.type) {
            case 'success': return 'bg-green-50 border-green-200';
            case 'error': return 'bg-red-50 border-red-200';
            case 'info': return 'bg-blue-50 border-blue-200';
            case 'warning': return 'bg-amber-50 border-amber-200';
          }
        };

        return (
          <div
            key={toast.id}
            className={`flex items-center gap-3 p-4 border rounded-lg shadow-md transition-all duration-300 animate-in fade-in slide-in-from-bottom-5 ${getBgColor()}`}
          >
            {getIcon()}
            <p className="text-gray-800 font-medium text-sm">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="ml-auto text-gray-500 hover:text-gray-700 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};

export default Toast;
