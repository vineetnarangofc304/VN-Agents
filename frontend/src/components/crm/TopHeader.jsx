import { useState } from "react";
import { ChevronDown, Plus, UserCircle } from "lucide-react";
import axios from "axios";

const VIEW_TITLES = {
  dashboard: "Dashboard",
  pipeline: "Pipeline",
  search: "Search",
  contacts: "Contacts",
  messages: "Messages",
  settings: "Settings",
};

export default function TopHeader({ accounts, activeAccountId, setActiveAccountId, activeView, fetchAccounts, API }) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [creating, setCreating] = useState(false);

  const activeAccount = accounts.find(a => a.account_id === activeAccountId);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await axios.post(`${API}/li-search/accounts`, { name: newName.trim(), linkedin_url: newUrl.trim() });
      await fetchAccounts();
      setNewName(""); setNewUrl(""); setShowAddForm(false);
    } catch (err) { console.error(err); }
    finally { setCreating(false); }
  };

  return (
    <header
      data-testid="crm-top-header"
      className="flex items-center justify-between h-14 px-6 border-b backdrop-blur-xl"
      style={{ background: "rgba(24,24,27,0.8)", borderColor: "#27272a" }}
    >
      {/* View Title */}
      <h1 className="text-lg font-semibold text-white tracking-tight" style={{ fontFamily: "'Manrope', sans-serif" }}>
        {VIEW_TITLES[activeView] || "Dashboard"}
      </h1>

      {/* Account Switcher */}
      <div className="relative">
        <button
          data-testid="account-switcher"
          onClick={() => setShowDropdown(!showDropdown)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md border text-sm transition-colors duration-150"
          style={{ borderColor: "#27272a", color: "#fff", background: "#18181b" }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "#27272a"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "#18181b"; }}
        >
          <UserCircle size={16} style={{ color: "#2563eb" }} />
          <span className="max-w-[140px] truncate">{activeAccount?.name || "Select Account"}</span>
          <ChevronDown size={14} style={{ color: "#a1a1aa" }} />
        </button>

        {showDropdown && (
          <div
            className="absolute right-0 top-full mt-1 w-64 rounded-md border shadow-xl z-50"
            style={{ background: "#18181b", borderColor: "#27272a" }}
          >
            {accounts.map(acc => (
              <button
                key={acc.account_id}
                data-testid={`account-option-${acc.account_id}`}
                onClick={() => { setActiveAccountId(acc.account_id); setShowDropdown(false); }}
                className="w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 transition-colors duration-150"
                style={{
                  color: acc.account_id === activeAccountId ? "#2563eb" : "#fff",
                  background: acc.account_id === activeAccountId ? "#27272a" : "transparent",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#27272a"; }}
                onMouseLeave={(e) => { if (acc.account_id !== activeAccountId) e.currentTarget.style.background = "transparent"; }}
              >
                <UserCircle size={14} />
                <span className="truncate">{acc.name}</span>
              </button>
            ))}
            <div className="border-t" style={{ borderColor: "#27272a" }}>
              {!showAddForm ? (
                <button
                  data-testid="add-account-btn"
                  onClick={() => setShowAddForm(true)}
                  className="w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 transition-colors duration-150"
                  style={{ color: "#a1a1aa" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "#27272a"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  <Plus size={14} /> Add Account
                </button>
              ) : (
                <div className="p-3 space-y-2">
                  <input
                    data-testid="new-account-name"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Name"
                    className="w-full px-3 py-1.5 rounded text-sm border"
                    style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}
                  />
                  <input
                    data-testid="new-account-url"
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                    placeholder="LinkedIn URL (optional)"
                    className="w-full px-3 py-1.5 rounded text-sm border"
                    style={{ background: "#09090b", borderColor: "#27272a", color: "#fff" }}
                  />
                  <div className="flex gap-2">
                    <button
                      data-testid="create-account-btn"
                      onClick={handleCreate}
                      disabled={creating}
                      className="flex-1 py-1.5 rounded text-sm font-medium text-white transition-colors duration-150"
                      style={{ background: "#2563eb" }}
                    >
                      {creating ? "..." : "Create"}
                    </button>
                    <button
                      onClick={() => setShowAddForm(false)}
                      className="px-3 py-1.5 rounded text-sm border"
                      style={{ borderColor: "#27272a", color: "#a1a1aa" }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
