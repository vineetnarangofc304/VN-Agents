import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import Sidebar from "./Sidebar";
import TopHeader from "./TopHeader";
import DashboardView from "./DashboardView";
import PipelineView from "./PipelineView";
import SearchView from "./SearchView";
import ContactsView from "./ContactsView";
import MessagesView from "./MessagesView";
import SettingsView from "./SettingsView";
import CompanyPagesView from "./CompanyPagesView";
import CampaignsView from "./CampaignsView";
import WhatsAppView from "./WhatsAppView";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CRMLayout() {
  const [activeView, setActiveView] = useState("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Multi-account state
  const [accounts, setAccounts] = useState([]);
  const [activeAccountId, setActiveAccountId] = useState("");
  const [cookieStatus, setCookieStatus] = useState(null);

  // Global stats
  const [stats, setStats] = useState({});

  const fetchAccounts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/li-search/accounts`);
      const accs = res.data.accounts || [];
      setAccounts(accs);
      if (accs.length > 0 && !activeAccountId) {
        setActiveAccountId(accs[0].account_id);
      }
    } catch (err) { console.error(err); }
  }, [activeAccountId]);

  const fetchCookieStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/li-search/cookie`);
      setCookieStatus(res.data);
    } catch (err) { console.error(err); }
  }, []);

  const fetchStats = useCallback(async () => {
    if (!activeAccountId) return;
    try {
      const res = await axios.get(`${API}/li-search/connections/stats/overview`, {
        params: { account_id: activeAccountId }
      });
      setStats(res.data);
    } catch (err) { console.error(err); }
  }, [activeAccountId]);

  useEffect(() => { fetchAccounts(); fetchCookieStatus(); }, [fetchAccounts, fetchCookieStatus]);
  useEffect(() => { if (activeAccountId) fetchStats(); }, [activeAccountId, fetchStats]);

  const sharedProps = {
    API, accounts, activeAccountId, setActiveAccountId,
    cookieStatus, setCookieStatus, stats, fetchStats,
    fetchAccounts, fetchCookieStatus
  };

  const views = {
    dashboard: <DashboardView {...sharedProps} />,
    pipeline: <PipelineView {...sharedProps} />,
    search: <SearchView {...sharedProps} />,
    contacts: <ContactsView {...sharedProps} />,
    messages: <MessagesView {...sharedProps} />,
    company_pages: <CompanyPagesView />,
    campaigns: <CampaignsView />,
    whatsapp: <WhatsAppView API={API} activeAccountId={activeAccountId} />,
    settings: <SettingsView {...sharedProps} />,
  };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#09090b", fontFamily: "'IBM Plex Sans', sans-serif" }}>
      <Sidebar
        activeView={activeView}
        setActiveView={setActiveView}
        collapsed={sidebarCollapsed}
        setCollapsed={setSidebarCollapsed}
        stats={stats}
        cookieStatus={cookieStatus}
      />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader
          accounts={accounts}
          activeAccountId={activeAccountId}
          setActiveAccountId={setActiveAccountId}
          activeView={activeView}
          fetchAccounts={fetchAccounts}
          API={API}
        />
        <main className="flex-1 overflow-y-auto p-6" style={{ background: "#09090b" }}>
          {views[activeView] || views.dashboard}
        </main>
      </div>
    </div>
  );
}
