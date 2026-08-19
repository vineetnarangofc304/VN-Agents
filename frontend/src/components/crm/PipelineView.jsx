import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { GitBranch, UserPlus, MessageSquare, CheckCircle, Clock, XCircle, ArrowRight } from "lucide-react";

const STAGES = [
  { id: "new_lead", label: "New Lead", color: "#2563eb", icon: UserPlus },
  { id: "connected", label: "Connected", color: "#8b5cf6", icon: CheckCircle },
  { id: "messaged", label: "Messaged", color: "#f59e0b", icon: MessageSquare },
  { id: "replied", label: "Replied", color: "#10b981", icon: ArrowRight },
  { id: "follow_up", label: "Follow-up", color: "#ef4444", icon: Clock },
  { id: "converted", label: "Converted", color: "#22c55e", icon: CheckCircle },
];

export default function PipelineView({ API, activeAccountId }) {
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchContacts = useCallback(async () => {
    if (!activeAccountId) return;
    setLoading(true);
    try {
      const res = await axios.get(`${API}/li-search/connections`, {
        params: { start: 0, count: 200, account_id: activeAccountId }
      });
      setContacts(res.data.connections || []);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [API, activeAccountId]);

  useEffect(() => { fetchContacts(); }, [fetchContacts]);

  // Assign stage based on contact data
  const getStage = (c) => {
    if (c.lead_stage) return c.lead_stage;
    if (c.messages_sent > 0 && c.last_reply_at) return "replied";
    if (c.messages_sent > 0) return "messaged";
    if (c.is_connection) return "connected";
    return "new_lead";
  };

  const stageContacts = {};
  STAGES.forEach(s => { stageContacts[s.id] = []; });
  contacts.forEach(c => {
    const stage = getStage(c);
    if (stageContacts[stage]) stageContacts[stage].push(c);
    else stageContacts.new_lead.push(c);
  });

  const handleMoveStage = async (contactId, newStage) => {
    try {
      await axios.put(`${API}/li-search/connections/${contactId}/stage`, {
        stage: newStage, account_id: activeAccountId
      });
      fetchContacts();
    } catch (err) { console.error(err); }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" style={{ color: "#a1a1aa" }}>
        <div className="animate-spin w-6 h-6 border-2 border-current border-t-transparent rounded-full mr-3" />
        Loading pipeline...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <GitBranch size={18} style={{ color: "#2563eb" }} />
        <h2 className="text-lg font-semibold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
          Lead Pipeline
        </h2>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#27272a", color: "#a1a1aa" }}>
          {contacts.length} contacts
        </span>
      </div>

      {/* Kanban Board */}
      <div className="flex gap-4 overflow-x-auto pb-4" style={{ minHeight: 500 }}>
        {STAGES.map((stage) => {
          const Icon = stage.icon;
          const items = stageContacts[stage.id];
          return (
            <div
              key={stage.id}
              data-testid={`pipeline-stage-${stage.id}`}
              className="flex-shrink-0 w-[260px] rounded-md border"
              style={{ background: "#18181b", borderColor: "#27272a" }}
            >
              {/* Stage Header */}
              <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: "#27272a" }}>
                <div className="flex items-center gap-2">
                  <Icon size={14} style={{ color: stage.color }} />
                  <span className="text-sm font-semibold text-white">{stage.label}</span>
                </div>
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded-full"
                  style={{ background: `${stage.color}20`, color: stage.color }}
                >
                  {items.length}
                </span>
              </div>

              {/* Stage Cards */}
              <div className="p-2 space-y-2 max-h-[400px] overflow-y-auto">
                {items.length === 0 ? (
                  <div className="text-center py-6">
                    <p className="text-xs" style={{ color: "#a1a1aa" }}>No contacts</p>
                  </div>
                ) : items.slice(0, 20).map((contact, i) => (
                  <div
                    key={contact.public_id || i}
                    className="rounded border p-3 cursor-pointer transition-colors duration-150"
                    style={{ background: "#09090b", borderColor: "#27272a" }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = stage.color; }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#27272a"; }}
                  >
                    <p className="text-sm font-medium text-white truncate">{contact.full_name || contact.name || "Unknown"}</p>
                    <p className="text-xs truncate mt-0.5" style={{ color: "#a1a1aa" }}>
                      {contact.occupation || contact.headline || ""}
                    </p>
                    {contact.company && (
                      <p className="text-xs mt-1" style={{ color: "#2563eb" }}>{contact.company}</p>
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      {contact.messages_sent > 0 && (
                        <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "#f59e0b20", color: "#f59e0b" }}>
                          {contact.messages_sent} msg
                        </span>
                      )}
                      {contact.email && (
                        <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "#10b98120", color: "#10b981" }}>
                          email
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
