import { AuthProvider, useAuth } from "./AuthContext";
import LoginPage from "./LoginPage";
import CRMDashboard from "./CRMDashboard";
import { Loader2 } from "lucide-react";

function CRMContent() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={28} className="animate-spin text-blue-600" />
          <span className="text-sm text-slate-500">Loading LinkedLeads.ai...</span>
        </div>
      </div>
    );
  }

  if (!user) return <LoginPage />;
  return <CRMDashboard />;
}

export default function LinkedInCRM() {
  return (
    <AuthProvider>
      <CRMContent />
    </AuthProvider>
  );
}
