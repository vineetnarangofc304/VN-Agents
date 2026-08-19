import { useNavigate } from "react-router-dom";
import { Receipt, RefreshCw, TrendingUp, Linkedin, BookOpen, ShieldCheck, Radar, SearchCheck, Zap, Landmark } from "lucide-react";

const agents = [
  { id: "invoicing", name: "Invoicing Agent", desc: "Process Google Play receipts, extract pages, download as ZIP", icon: Receipt, color: "#3b82f6", path: "/invoicing" },
  { id: "refund", name: "Refund Agent", desc: "Generate detailed refund requests for failed transactions", icon: RefreshCw, color: "#f59e0b", path: "/refund" },
  { id: "stocks", name: "Stock Investor", desc: "Scan NSE stocks, find undervalued picks under INR 100", icon: TrendingUp, color: "#16a34a", path: "/stocks" },
  { id: "linkedin", name: "LinkedIn Agent", desc: "Auto-generate and publish LinkedIn posts for your companies", icon: Linkedin, color: "#0a66c2", path: "/linkedin" },
  { id: "linkedin-search", name: "LinkedIn Lead CRM", desc: "Full CRM: find leads, manage pipeline, send messages, auto-comment", icon: SearchCheck, color: "#2563eb", path: "/linkedin-search" },
  { id: "content-studio", name: "Content Studio", desc: "AI Personal Brand Content OS — research, create, publish thought leadership", icon: Zap, color: "#0066FF", path: "/content-studio" },
  { id: "directory", name: "PDF Extractor", desc: "Extract company data from PDF directories into Excel", icon: BookOpen, color: "#8b5cf6", path: "/directory" },
  { id: "checker", name: "Account Checker", desc: "Bulk-test login accounts and find active ones", icon: ShieldCheck, color: "#ef4444", path: "/checker" },
  { id: "catchment", name: "Catchment Mining", desc: "Crawl web for contact databases — RWA, clubs, govt directories across Delhi NCR", icon: Radar, color: "#14b8a6", path: "/catchment" },
  { id: "banking", name: "Banking Agent", desc: "Upload bank statements, analyze spending, merchants, categories & cash flow trends", icon: Landmark, color: "#0d9488", path: "/banking" },
];

const LandingPage = () => {
  const navigate = useNavigate();

  return (
    <div className="landing-container" data-testid="landing-page">
      <div className="landing-header">
        <h1>Agent Hub</h1>
        <p>Select an agent to get started</p>
      </div>
      <div className="landing-grid">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className="landing-card"
            onClick={() => navigate(agent.path)}
            data-testid={`landing-card-${agent.id}`}
          >
            <div className="landing-card-icon" style={{ background: agent.color }}>
              <agent.icon size={28} color="#fff" />
            </div>
            <h2>{agent.name}</h2>
            <p>{agent.desc}</p>
            <span className="landing-card-arrow">&rarr;</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default LandingPage;
