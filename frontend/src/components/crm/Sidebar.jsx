import {
  LayoutDashboard, Search, GitBranch, Users, MessageSquare,
  Settings, ChevronLeft, ChevronRight, Zap, Circle, Building2, Megaphone, MessageSquareText
} from "lucide-react";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "pipeline", label: "Pipeline", icon: GitBranch },
  { id: "search", label: "Search", icon: Search },
  { id: "contacts", label: "Contacts", icon: Users },
  { id: "messages", label: "Messages", icon: MessageSquare },
  { id: "whatsapp", label: "WhatsApp", icon: MessageSquareText },
  { id: "campaigns", label: "Campaigns", icon: Megaphone },
  { id: "company_pages", label: "Company Pages", icon: Building2 },
  { id: "settings", label: "Settings", icon: Settings },
];

export default function Sidebar({ activeView, setActiveView, collapsed, setCollapsed, stats, cookieStatus }) {
  return (
    <aside
      data-testid="crm-sidebar"
      className="flex flex-col border-r transition-[width] duration-200"
      style={{
        width: collapsed ? 64 : 220,
        background: "#18181b",
        borderColor: "#27272a",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 h-14 border-b" style={{ borderColor: "#27272a" }}>
        <div className="w-8 h-8 rounded-md flex items-center justify-center" style={{ background: "#2563eb" }}>
          <Zap size={18} className="text-white" />
        </div>
        {!collapsed && (
          <span className="text-white font-bold text-base tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
            LeadCRM
          </span>
        )}
      </div>

      {/* Nav Items */}
      <nav className="flex-1 py-3 px-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = activeView === item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              data-testid={`nav-${item.id}`}
              onClick={() => setActiveView(item.id)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors duration-150"
              style={{
                background: isActive ? "#2563eb" : "transparent",
                color: isActive ? "#fff" : "#a1a1aa",
              }}
              onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = "#27272a"; }}
              onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
            >
              <Icon size={18} />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Connection Status */}
      <div className="px-3 py-3 border-t" style={{ borderColor: "#27272a" }}>
        <div className="flex items-center gap-2">
          <Circle
            size={8}
            fill={cookieStatus?.has_cookie ? "#10b981" : "#ef4444"}
            className={cookieStatus?.has_cookie ? "text-emerald-500" : "text-red-500"}
          />
          {!collapsed && (
            <span className="text-xs" style={{ color: "#a1a1aa" }}>
              {cookieStatus?.has_cookie ? cookieStatus.profile_name || "Connected" : "Not Connected"}
            </span>
          )}
        </div>
      </div>

      {/* Collapse Toggle */}
      <button
        data-testid="sidebar-toggle"
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-10 border-t transition-colors duration-150"
        style={{ borderColor: "#27272a", color: "#a1a1aa" }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "#27272a"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}
