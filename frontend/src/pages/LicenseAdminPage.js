import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const API = `${BACKEND_URL}/api`;

const adminAuth = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem("adminToken") || ""}` },
});

const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "—");

const StatusPill = ({ status }) => {
  const colors = {
    trial: "bg-blue-500/15 text-blue-300 border-blue-500/30",
    active: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    expired: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    revoked: "bg-red-500/15 text-red-300 border-red-500/30",
  };
  return (
    <span
      data-testid={`license-status-${status}`}
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${colors[status] || "bg-slate-500/15 text-slate-300 border-slate-500/30"}`}
    >
      {status || "—"}
    </span>
  );
};

export default function LicenseAdminPage() {
  const [tab, setTab] = useState("config");
  const [config, setConfig] = useState(null);
  const [savingCfg, setSavingCfg] = useState(false);
  const [cfgMsg, setCfgMsg] = useState("");
  const [licenses, setLicenses] = useState([]);
  const [licTotal, setLicTotal] = useState(0);
  const [licQuery, setLicQuery] = useState("");
  const [issueEmail, setIssueEmail] = useState("");
  const [issueDays, setIssueDays] = useState(31);
  const [busy, setBusy] = useState(false);

  const loadConfig = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/admin/license/config`, adminAuth());
      setConfig(r.data);
    } catch (e) {
      setCfgMsg(`Failed to load config: ${e.response?.data?.detail || e.message}`);
    }
  }, []);

  const loadLicenses = useCallback(async () => {
    try {
      const r = await axios.get(
        `${API}/admin/license/list?limit=200${licQuery ? `&q=${encodeURIComponent(licQuery)}` : ""}`,
        adminAuth(),
      );
      setLicenses(r.data.items || []);
      setLicTotal(r.data.total || 0);
    } catch (e) {
      setLicenses([]);
    }
  }, [licQuery]);

  useEffect(() => {
    loadConfig();
    loadLicenses();
  }, [loadConfig, loadLicenses]);

  const saveConfig = async () => {
    setSavingCfg(true);
    setCfgMsg("");
    try {
      const patch = {
        product_name: config.product_name,
        monthly_price: Number(config.monthly_price),
        currency: (config.currency || "usd").toLowerCase(),
        trial_days: Number(config.trial_days),
        max_pcs_per_license: Number(config.max_pcs_per_license),
        enabled: !!config.enabled,
        admin_contact_email: config.admin_contact_email || "",
        admin_contact_message: config.admin_contact_message || "",
      };
      const r = await axios.put(`${API}/admin/license/config`, patch, adminAuth());
      setConfig(r.data);
      setCfgMsg("✓ Saved. Changes apply globally to all installers and apps immediately.");
    } catch (e) {
      setCfgMsg(`✗ Save failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setSavingCfg(false);
    }
  };

  const revoke = async (key) => {
    if (!window.confirm(`Revoke license ${key}? This blocks the customer's PC immediately.`)) return;
    setBusy(true);
    try {
      await axios.post(`${API}/admin/license/revoke/${encodeURIComponent(key)}`, {}, adminAuth());
      await loadLicenses();
    } finally {
      setBusy(false);
    }
  };

  const extend = async (key) => {
    const d = window.prompt(`Extend ${key} by how many days?`, "31");
    if (!d) return;
    setBusy(true);
    try {
      await axios.post(`${API}/admin/license/extend/${encodeURIComponent(key)}?days=${parseInt(d, 10)}`, {}, adminAuth());
      await loadLicenses();
    } finally {
      setBusy(false);
    }
  };

  const issue = async () => {
    if (!issueEmail) return;
    setBusy(true);
    try {
      const r = await axios.post(
        `${API}/admin/license/issue?email=${encodeURIComponent(issueEmail)}&days=${issueDays}`,
        {},
        adminAuth(),
      );
      alert(`Issued: ${r.data.license_key}`);
      setIssueEmail("");
      await loadLicenses();
    } catch (e) {
      alert(`Failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="license-admin-page" className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-6xl mx-auto">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">License & Subscription</h1>
            <p className="text-slate-400 mt-1 text-sm">
              Global controls — every customer install reads from here in real time.
            </p>
          </div>
          <a
            href="/admin/dashboard"
            data-testid="back-to-admin-dashboard"
            className="text-slate-400 hover:text-white text-sm border border-slate-700 px-3 py-1.5 rounded-md"
          >
            ← Back to Admin
          </a>
        </header>

        <div className="flex gap-2 border-b border-slate-800 mb-6">
          <button
            data-testid="tab-config"
            className={`px-4 py-2 text-sm font-medium ${tab === "config" ? "text-white border-b-2 border-blue-500" : "text-slate-400 hover:text-white"}`}
            onClick={() => setTab("config")}
          >
            Pricing & Rules
          </button>
          <button
            data-testid="tab-licenses"
            className={`px-4 py-2 text-sm font-medium ${tab === "licenses" ? "text-white border-b-2 border-blue-500" : "text-slate-400 hover:text-white"}`}
            onClick={() => setTab("licenses")}
          >
            Customers / Licenses ({licTotal})
          </button>
        </div>

        {tab === "config" && config && (
          <section data-testid="config-section" className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <Field label="Product name">
                <input
                  data-testid="cfg-product-name"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                  value={config.product_name || ""}
                  onChange={(e) => setConfig({ ...config, product_name: e.target.value })}
                />
              </Field>
              <Field label={`Monthly price (${(config.currency || "usd").toUpperCase()})`}>
                <input
                  data-testid="cfg-price"
                  type="number"
                  step="0.01"
                  min="0.5"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                  value={config.monthly_price || 0}
                  onChange={(e) => setConfig({ ...config, monthly_price: e.target.value })}
                />
              </Field>
              <Field label="Currency (3-letter ISO)">
                <input
                  data-testid="cfg-currency"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm uppercase"
                  maxLength={3}
                  value={(config.currency || "usd").toUpperCase()}
                  onChange={(e) => setConfig({ ...config, currency: e.target.value.toLowerCase() })}
                />
              </Field>
              <Field label="Trial days (0 = no trial)">
                <input
                  data-testid="cfg-trial-days"
                  type="number"
                  min="0"
                  max="365"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                  value={config.trial_days ?? 0}
                  onChange={(e) => setConfig({ ...config, trial_days: e.target.value })}
                />
              </Field>
              <Field label="Max PCs per license">
                <input
                  data-testid="cfg-max-pcs"
                  type="number"
                  min="1"
                  max="1000"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                  value={config.max_pcs_per_license || 1}
                  onChange={(e) => setConfig({ ...config, max_pcs_per_license: e.target.value })}
                />
              </Field>
              <Field label="Licensing master switch">
                <label className="flex items-center gap-3 mt-2">
                  <input
                    data-testid="cfg-enabled"
                    type="checkbox"
                    checked={!!config.enabled}
                    onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                    className="w-5 h-5 rounded"
                  />
                  <span className="text-sm text-slate-300">
                    {config.enabled ? "ENABLED — installer requires a license" : "DISABLED — open install (no license check)"}
                  </span>
                </label>
              </Field>
            </div>

            <div className="border-t border-slate-800 pt-5 space-y-4">
              <h3 className="text-sm uppercase tracking-wider text-slate-400 font-semibold">
                Manual Purchase — Contact Details
              </h3>
              <p className="text-xs text-slate-500">
                Customers click "Contact Admin to Buy" in the installer. Set the email + instructions you want them to see.
              </p>
              <Field label="Admin contact email (shown to customers)">
                <input
                  data-testid="cfg-admin-email"
                  type="email"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                  value={config.admin_contact_email || ""}
                  onChange={(e) => setConfig({ ...config, admin_contact_email: e.target.value })}
                  placeholder="you@example.com"
                />
              </Field>
              <Field label="Instructions to customer (payment methods, etc.)">
                <textarea
                  data-testid="cfg-admin-message"
                  rows={5}
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                  value={config.admin_contact_message || ""}
                  onChange={(e) => setConfig({ ...config, admin_contact_message: e.target.value })}
                  placeholder="To purchase, email us with your details and we'll reply with a license key after payment is received. We accept: Bitcoin, USDT (TRC20), bank transfer..."
                />
              </Field>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-slate-800">
              <span className="text-xs text-slate-500">
                Last updated: {fmt(config.updated_at)}
              </span>
              <button
                data-testid="cfg-save-btn"
                disabled={savingCfg}
                onClick={saveConfig}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white px-5 py-2 rounded-md text-sm font-medium"
              >
                {savingCfg ? "Saving…" : "Save Globally"}
              </button>
            </div>
            {cfgMsg && (
              <div data-testid="cfg-message" className="text-sm text-slate-300">{cfgMsg}</div>
            )}
          </section>
        )}

        {tab === "licenses" && (
          <section data-testid="licenses-section" className="space-y-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-wrap items-end gap-3">
              <Field label="Search (email, key, machine)" className="flex-1 min-w-[260px]">
                <input
                  data-testid="lic-search"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                  value={licQuery}
                  onChange={(e) => setLicQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadLicenses()}
                  placeholder="user@example.com or RFLW-…"
                />
              </Field>
              <button
                data-testid="lic-refresh"
                onClick={loadLicenses}
                className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-md text-sm"
              >
                Search
              </button>

              <div className="border-l border-slate-800 pl-4 flex flex-wrap items-end gap-2">
                <Field label="Issue manual license (email)">
                  <input
                    data-testid="issue-email"
                    type="email"
                    className="bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                    value={issueEmail}
                    onChange={(e) => setIssueEmail(e.target.value)}
                    placeholder="customer@example.com"
                  />
                </Field>
                <Field label="Days">
                  <input
                    data-testid="issue-days"
                    type="number"
                    min="1"
                    max="3650"
                    className="w-24 bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm"
                    value={issueDays}
                    onChange={(e) => setIssueDays(parseInt(e.target.value, 10) || 31)}
                  />
                </Field>
                <button
                  data-testid="issue-btn"
                  onClick={issue}
                  disabled={busy || !issueEmail}
                  className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white px-4 py-2 rounded-md text-sm"
                >
                  Issue
                </button>
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-900/80 text-slate-400 text-xs uppercase tracking-wider">
                  <tr>
                    <th className="text-left px-3 py-2">License Key</th>
                    <th className="text-left px-3 py-2">Email</th>
                    <th className="text-left px-3 py-2">Status</th>
                    <th className="text-left px-3 py-2">Machine</th>
                    <th className="text-left px-3 py-2">Activated</th>
                    <th className="text-left px-3 py-2">Expires</th>
                    <th className="text-right px-3 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {licenses.length === 0 && (
                    <tr>
                      <td colSpan={7} className="text-center text-slate-500 py-8">
                        No licenses yet. Customers will appear here after they start a trial or buy.
                      </td>
                    </tr>
                  )}
                  {licenses.map((l) => (
                    <tr key={l.license_key} className="border-t border-slate-800/70 hover:bg-slate-900/30">
                      <td className="px-3 py-2 font-mono text-xs">{l.license_key}</td>
                      <td className="px-3 py-2">{l.email}</td>
                      <td className="px-3 py-2"><StatusPill status={l.status} /></td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {l.machine_id ? `${l.machine_id.slice(0, 14)}…` : <span className="text-slate-500">unbound</span>}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-400">{fmt(l.activated_at)}</td>
                      <td className="px-3 py-2 text-xs text-slate-400">
                        {fmt(l.subscription_ends_at || l.trial_ends_at)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          data-testid={`extend-${l.license_key}`}
                          onClick={() => extend(l.license_key)}
                          disabled={busy}
                          className="text-xs px-2 py-1 mr-1 bg-blue-600/20 hover:bg-blue-600/40 border border-blue-700/40 rounded"
                        >
                          Extend
                        </button>
                        {l.status !== "revoked" && (
                          <button
                            data-testid={`revoke-${l.license_key}`}
                            onClick={() => revoke(l.license_key)}
                            disabled={busy}
                            className="text-xs px-2 py-1 bg-red-600/20 hover:bg-red-600/40 border border-red-700/40 rounded"
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

const Field = ({ label, children, className = "" }) => (
  <label className={`block ${className}`}>
    <div className="text-xs uppercase tracking-wider text-slate-400 mb-1.5">{label}</div>
    {children}
  </label>
);
