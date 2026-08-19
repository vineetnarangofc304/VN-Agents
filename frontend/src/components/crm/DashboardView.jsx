import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Users, MessageSquare, UserPlus, TrendingUp, Search, Send, Clock } from "lucide-react";

export default function DashboardView({ API, activeAccountId, stats }) {
  const [recentMessages, setRecentMessages] = useState([]);
  const [recentPosts, setRecentPosts] = useState([]);

  const fetchRecent = useCallback(async () => {
    if (!activeAccountId) return;
    try {
      const [msgRes, postRes] = await Promise.all([
        axios.get(`${API}/li-search/messages/log`, { params: { start: 0, count: 10, account_id: activeAccountId } }),
        axios.get(`${API}/li-search/posts`, { params: { limit: 5 } }),
      ]);
      setRecentMessages(msgRes.data.messages || []);
      setRecentPosts(postRes.data.posts || []);
    } catch (err) { console.error(err); }
  }, [API, activeAccountId]);

  useEffect(() => { fetchRecent(); }, [fetchRecent]);

  const kpis = [
    { label: "Total Contacts", value: stats.total_contacts || 0, icon: Users, color: "#2563eb" },
    { label: "Messages Sent", value: stats.total_messages_sent || 0, icon: Send, color: "#10b981" },
    { label: "Contacted", value: stats.contacted || 0, icon: MessageSquare, color: "#f59e0b" },
    { label: "Response Rate", value: stats.contacted && stats.total_contacts ? `${Math.round((stats.contacted / stats.total_contacts) * 100)}%` : "—", icon: TrendingUp, color: "#8b5cf6" },
  ];

  return (
    <div className="space-y-6 max-w-7xl">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, i) => {
          const Icon = kpi.icon;
          return (
            <div
              key={i}
              data-testid={`kpi-${kpi.label.toLowerCase().replace(/\s/g, "-")}`}
              className="rounded-md border p-5 transition-transform duration-150 hover:-translate-y-0.5"
              style={{ background: "#18181b", borderColor: "#27272a" }}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs uppercase tracking-[0.2em] font-medium" style={{ color: "#a1a1aa" }}>
                  {kpi.label}
                </span>
                <div className="w-8 h-8 rounded-md flex items-center justify-center" style={{ background: `${kpi.color}20` }}>
                  <Icon size={16} style={{ color: kpi.color }} />
                </div>
              </div>
              <p className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
                {kpi.value}
              </p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Messages */}
        <div className="rounded-md border" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <div className="px-5 py-4 border-b flex items-center gap-2" style={{ borderColor: "#27272a" }}>
            <MessageSquare size={16} style={{ color: "#2563eb" }} />
            <h3 className="text-sm font-semibold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>Recent Messages</h3>
          </div>
          <div className="divide-y" style={{ borderColor: "#27272a" }}>
            {recentMessages.length === 0 ? (
              <div className="px-5 py-8 text-center" style={{ color: "#a1a1aa" }}>
                <MessageSquare size={24} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">No messages sent yet</p>
              </div>
            ) : recentMessages.slice(0, 5).map((msg, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between" style={{ borderColor: "#27272a" }}>
                <div>
                  <p className="text-sm font-medium text-white">{msg.recipient_name || "Unknown"}</p>
                  <p className="text-xs truncate max-w-[250px]" style={{ color: "#a1a1aa" }}>{msg.message?.substring(0, 60)}...</p>
                </div>
                <div className="flex items-center gap-1 text-xs" style={{ color: "#a1a1aa" }}>
                  <Clock size={12} />
                  {msg.sent_at ? new Date(msg.sent_at).toLocaleDateString() : ""}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Leads Found */}
        <div className="rounded-md border" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <div className="px-5 py-4 border-b flex items-center gap-2" style={{ borderColor: "#27272a" }}>
            <Search size={16} style={{ color: "#10b981" }} />
            <h3 className="text-sm font-semibold text-white" style={{ fontFamily: "'Manrope', sans-serif" }}>Recent Leads</h3>
          </div>
          <div className="divide-y" style={{ borderColor: "#27272a" }}>
            {recentPosts.length === 0 ? (
              <div className="px-5 py-8 text-center" style={{ color: "#a1a1aa" }}>
                <Search size={24} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">No leads found yet. Run a search.</p>
              </div>
            ) : recentPosts.slice(0, 5).map((post, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between" style={{ borderColor: "#27272a" }}>
                <div>
                  <p className="text-sm font-medium text-white">{post.author_name || "Unknown"}</p>
                  <p className="text-xs truncate max-w-[250px]" style={{ color: "#a1a1aa" }}>{post.post_text?.substring(0, 60)}...</p>
                </div>
                <span
                  className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{
                    background: post.relevance === "high" ? "#10b98120" : post.relevance === "medium" ? "#f59e0b20" : "#ef444420",
                    color: post.relevance === "high" ? "#10b981" : post.relevance === "medium" ? "#f59e0b" : "#ef4444",
                  }}
                >
                  {post.relevance || "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
