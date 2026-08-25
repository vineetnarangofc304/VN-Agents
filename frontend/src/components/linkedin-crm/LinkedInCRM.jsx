import { AuthProvider, useAuth } from "./AuthContext";
import LoginPage from "./LoginPage";
import CRMDashboard from "./CRMDashboard";
import { Loader2 } from "lucide-react";

function CRMContent() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#09090b" }}>
        <Loader2 size={24} className="animate-spin" style={{ color: "#2563eb" }} />
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
