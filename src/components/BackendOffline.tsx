import { WifiOff, RefreshCw } from 'lucide-react';

interface BackendOfflineProps {
  error: string;
  onRetry: () => void;
}

export default function BackendOffline({ error, onRetry }: BackendOfflineProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
      <div className="bg-red-50 border border-red-200 rounded-2xl p-8 max-w-lg w-full">
        <div className="flex justify-center mb-4">
          <div className="bg-red-100 p-4 rounded-full">
            <WifiOff className="w-8 h-8 text-red-500" />
          </div>
        </div>
        <h2 className="text-xl font-bold text-red-800 mb-2">Backend Offline</h2>
        <p className="text-sm text-red-700 mb-4">
          Cannot connect to the FastAPI server. Please start it:
        </p>
        <pre className="bg-red-900 text-green-300 rounded-lg p-3 text-xs text-left mb-4 overflow-x-auto">
          cd backend{"\n"}
          uvicorn main:app --reload --port 8000
        </pre>
        <p className="text-xs text-red-500 mb-4 font-mono break-all">{error}</p>
        <button
          onClick={onRetry}
          className="flex items-center gap-2 mx-auto px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm font-medium"
        >
          <RefreshCw className="w-4 h-4" />
          Retry Connection
        </button>
      </div>
    </div>
  );
}
