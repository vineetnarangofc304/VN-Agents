import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Send, Loader2, Users, CheckCircle, XCircle, Clock, Play, ChevronDown, ChevronUp } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CampaignsView() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedCampaign, setExpandedCampaign] = useState(null);
  const [prospects, setProspects] = useState({});
  const [sending, setSending] = useState(null);
  const [sendResult, setSendResult] = useState(null);

  const fetchCampaigns = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/campaigns`);
      setCampaigns(res.data.campaigns || []);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, []);

  const fetchProspects = useCallback(async (campaignId) => {
    try {
      const res = await axios.get(`${API}/campaigns/${campaignId}/prospects?limit=50`);
      setProspects(prev => ({ ...prev, [campaignId]: res.data }));
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  const handleSendBatch = async (campaignId, batchSize = 10) => {
    setSending(campaignId);
    setSendResult(null);
    try {
      const res = await axios.post(`${API}/campaigns/${campaignId}/send-batch`, { batch_size: batchSize });
      setSendResult(res.data);
      fetchCampaigns();
      fetchProspects(campaignId);
    } catch (err) {
      setSendResult({ success: false, detail: err.response?.data?.detail || "Failed" });
    }
    finally { setSending(null); }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" style={{ color: "#a1a1aa" }}>
        <Loader2 size={20} className="animate-spin mr-2" /> Loading campaigns...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center gap-2">
        <Send size={20} style={{ color: "#2563eb" }} />
        <h2 className="text-xl font-bold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
          Outreach Campaigns
        </h2>
      </div>

      {campaigns.length === 0 ? (
        <div className="text-center py-12 rounded-md border" style={{ background: "#18181b", borderColor: "#27272a" }}>
          <Send size={32} className="mx-auto mb-3 opacity-30" style={{ color: "#a1a1aa" }} />
          <p className="text-sm" style={{ color: "#a1a1aa" }}>No campaigns yet</p>
        </div>
      ) : campaigns.map(campaign => (
        <div key={campaign.campaign_id} data-testid={`campaign-${campaign.campaign_id}`}
          className="rounded-md border overflow-hidden" style={{ background: "#18181b", borderColor: "#27272a" }}>

          {/* Campaign Header */}
          <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: "#27272a" }}>
            <div>
              <h3 className="text-sm font-semibold text-white">{campaign.name}</h3>
              <p className="text-xs mt-1" style={{ color: "#a1a1aa" }}>
                Created {new Date(campaign.created_at).toLocaleDateString()} | Limit: {campaign.daily_limit}/day
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                data-testid={`send-batch-${campaign.campaign_id}`}
                onClick={() => handleSendBatch(campaign.campaign_id, 10)}
                disabled={sending === campaign.campaign_id || campaign.pending === 0}
                className="px-4 py-2 rounded-md text-sm font-medium text-white flex items-center gap-2 disabled:opacity-40"
                style={{ background: "#2563eb" }}
              >
                {sending === campaign.campaign_id ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                Send Batch (10)
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="px-5 py-3 flex items-center gap-6 border-b" style={{ borderColor: "#27272a" }}>
            <div className="flex items-center gap-1">
              <Users size={14} style={{ color: "#a1a1aa" }} />
              <span className="text-xs text-white font-medium">{campaign.total}</span>
              <span className="text-xs" style={{ color: "#a1a1aa" }}>total</span>
            </div>
            <div className="flex items-center gap-1">
              <Clock size={14} style={{ color: "#f59e0b" }} />
              <span className="text-xs font-medium" style={{ color: "#f59e0b" }}>{campaign.pending}</span>
              <span className="text-xs" style={{ color: "#a1a1aa" }}>pending</span>
            </div>
            <div className="flex items-center gap-1">
              <CheckCircle size={14} style={{ color: "#10b981" }} />
              <span className="text-xs font-medium" style={{ color: "#10b981" }}>{campaign.sent}</span>
              <span className="text-xs" style={{ color: "#a1a1aa" }}>sent</span>
            </div>
            <div className="flex items-center gap-1">
              <XCircle size={14} style={{ color: "#ef4444" }} />
              <span className="text-xs font-medium" style={{ color: "#ef4444" }}>{campaign.failed}</span>
              <span className="text-xs" style={{ color: "#a1a1aa" }}>failed</span>
            </div>
            {/* Progress bar */}
            <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "#27272a" }}>
              <div className="h-full rounded-full" style={{
                background: "#10b981",
                width: `${campaign.total ? (campaign.sent / campaign.total * 100) : 0}%`
              }} />
            </div>
          </div>

          {/* Send Result */}
          {sendResult && sending === null && (
            <div className="px-5 py-2 text-xs" style={{ background: sendResult.success ? "#10b98110" : "#ef444410", color: sendResult.success ? "#10b981" : "#ef4444" }}>
              {sendResult.success ? `Sent: ${sendResult.sent} | Failed: ${sendResult.failed} | Remaining today: ${sendResult.daily_remaining}` : sendResult.detail}
            </div>
          )}

          {/* Expand/Collapse Prospects */}
          <div className="px-5 py-2">
            <button
              onClick={() => {
                if (expandedCampaign === campaign.campaign_id) {
                  setExpandedCampaign(null);
                } else {
                  setExpandedCampaign(campaign.campaign_id);
                  fetchProspects(campaign.campaign_id);
                }
              }}
              className="text-xs flex items-center gap-1" style={{ color: "#a1a1aa" }}
            >
              {expandedCampaign === campaign.campaign_id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {expandedCampaign === campaign.campaign_id ? "Hide" : "Show"} Prospects
            </button>
          </div>

          {/* Prospects Table */}
          {expandedCampaign === campaign.campaign_id && prospects[campaign.campaign_id] && (
            <div className="border-t overflow-x-auto" style={{ borderColor: "#27272a" }}>
              <table className="w-full">
                <thead>
                  <tr className="border-b" style={{ borderColor: "#27272a" }}>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>#</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Name</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Brand</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Title</th>
                    <th className="px-4 py-2 text-left text-xs" style={{ color: "#a1a1aa" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(prospects[campaign.campaign_id]?.prospects || []).map(p => (
                    <tr key={p.public_id} className="border-t" style={{ borderColor: "#27272a" }}>
                      <td className="px-4 py-2 text-xs text-white">{p.rank}</td>
                      <td className="px-4 py-2 text-xs text-white">
                        <a href={p.linkedin_url} target="_blank" rel="noreferrer" style={{ color: "#2563eb" }}>{p.name}</a>
                      </td>
                      <td className="px-4 py-2 text-xs" style={{ color: "#a1a1aa" }}>{p.brand}</td>
                      <td className="px-4 py-2 text-xs truncate max-w-[200px]" style={{ color: "#a1a1aa" }}>{p.title}</td>
                      <td className="px-4 py-2">
                        <span className="text-xs px-2 py-0.5 rounded-full" style={{
                          background: p.status === "sent" ? "#10b98120" : p.status === "failed" ? "#ef444420" : "#f59e0b20",
                          color: p.status === "sent" ? "#10b981" : p.status === "failed" ? "#ef4444" : "#f59e0b",
                        }}>{p.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
