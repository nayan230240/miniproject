
import React, { useEffect, useMemo, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  NavLink,
  useLocation,
} from "react-router-dom";

import Header from "./components/Header";
import Overview from "./components/Overview";
import ServerList from "./components/ServerList";
import DetailPanel from "./components/DetailPanel";
import BaselineManager from "./components/BaselineManager";
import DriftHistory from "./components/DriftHistory";
import AIInsights from "./components/AIInsights";
import { postJson } from "./api";
import useFleet from "./hooks/useFleet";
import "./App.css";

// --------------------------------------------------
// SETTINGS PAGE
// --------------------------------------------------

function SettingsPage() {
  const [pollInterval, setPollInterval] = useState(30);

  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("configo_theme") || "light";
    } catch {
      return "light";
    }
  });

  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  // Apply and persist the selected theme.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);

    try {
      localStorage.setItem("configo_theme", theme);
    } catch {
      // Theme remains active for the current session.
    }
  }, [theme]);

  const handleSave = () => {
    try {
      setSaving(true);
      setMessage("");

      localStorage.setItem("configo_theme", theme);

      setMessage(
        "Appearance settings saved successfully. Polling interval is a demo setting."
      );
    } catch {
      setMessage("Unable to save theme preference in this browser.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-page">

      {/* PAGE HEADING */}
      <div className="welcome-section">
        <div>
          <p className="eyebrow">APPLICATION MANAGEMENT</p>
          <h1>Settings</h1>
          <p>
            Customize Configo monitoring preferences and application
            appearance.
          </p>
        </div>
      </div>

      {message && (
        <div className="action-message" role="status">
          {message}
        </div>
      )}

      {/* MONITORING SETTINGS - DEMO ONLY */}
      <section className="majority-summary">
        <div className="section-heading">
          <div>
            <p className="eyebrow">MONITORING CONFIGURATION</p>
            <h2>Polling Interval</h2>
          </div>

          <span className="info-chip">Demo Setting</span>
        </div>

        <p className="majority-description">
          Select how frequently you would like Configo to scan
          server configurations. This setting is for demonstration
          purposes and does not change the actual backend polling schedule.
        </p>

        <div className="settings-control">
          <label htmlFor="poll-interval">Scan frequency</label>

          <select
            id="poll-interval"
            value={pollInterval}
            onChange={(event) =>
              setPollInterval(Number(event.target.value))
            }
          >
            {[10, 30, 60, 120, 300, 600, 1800, 3600].map(
              (seconds) => (
                <option key={seconds} value={seconds}>
                  {seconds < 60
                    ? `${seconds} seconds`
                    : `${seconds / 60} minute${seconds === 60 ? "" : "s"}`}
                </option>
              )
            )}
          </select>

          <p className="settings-help">
            Current demo selection: {pollInterval} seconds.
            Actual backend polling remains unchanged.
          </p>
        </div>
      </section>

      {/* APPEARANCE SETTINGS */}
      <section className="majority-summary">
        <div className="section-heading">
          <div>
            <p className="eyebrow">DISPLAY PREFERENCES</p>
            <h2>Application Theme</h2>
          </div>
        </div>

        <p className="majority-description">
          Choose your preferred appearance for the Configo dashboard.
          Your selection is remembered by this browser.
        </p>

        <div className="theme-options">
          <button
            type="button"
            className={`theme-option ${
              theme === "light" ? "selected" : ""
            }`}
            onClick={() => setTheme("light")}
          >
            <span className="theme-preview light-preview">☀</span>
            <strong>Light Mode</strong>
            <span>Bright and clean appearance</span>
          </button>

          <button
            type="button"
            className={`theme-option ${
              theme === "dark" ? "selected" : ""
            }`}
            onClick={() => setTheme("dark")}
          >
            <span className="theme-preview dark-preview">☾</span>
            <strong>Dark Mode</strong>
            <span>Dark and comfortable appearance</span>
          </button>
        </div>
      </section>

      {/* ABOUT CONFIGO / SYSTEM INFORMATION */}
      <section className="majority-summary">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PROJECT INFORMATION</p>
            <h2>About Configo</h2>
          </div>

          <span className="info-chip">System Overview</span>
        </div>

        <p className="majority-description">
          Configo is an AI-based Server Drift Detector designed
          to monitor server configurations, identify configuration
          differences, and help engineers investigate unexpected changes.
        </p>

        <div className="majority-grid">
          <div>
            <span>Project Name</span>
            <strong style={{ fontSize: "16px" }}>Configo</strong>
          </div>

          <div>
            <span>Project Type</span>
            <strong style={{ fontSize: "16px" }}>AI-based</strong>
          </div>

          <div>
            <span>Frontend</span>
            <strong style={{ fontSize: "16px" }}>React + Vite</strong>
          </div>

          <div>
            <span>Backend</span>
            <strong style={{ fontSize: "16px" }}>FastAPI</strong>
          </div>

          <div>
            <span>Database</span>
            <strong style={{ fontSize: "16px" }}>SQLite</strong>
          </div>

          <div>
            <span>AI Integration</span>
            <strong style={{ fontSize: "16px" }}>Gemini</strong>
          </div>
        </div>

        <p className="settings-help">
          Configo helps engineers detect server configuration drift
          and verify changes against an approved configuration baseline.
        </p>
      </section>

      {/* SAVE SETTINGS */}
      <div className="settings-save-area">
        <button
          type="button"
          className="settings-save-button"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>

    </section>
  );
}

// --------------------------------------------------
// DASHBOARD LAYOUT
// --------------------------------------------------

function DashboardLayout() {
  const {
    servers = [],
    drift = {},
    error,
    updatedAt,
    loading,
    reload,
  } = useFleet();

  const [selectedServerId, setSelectedServerId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const location = useLocation();
  const currentPath = location.pathname;

  const peerDriftIds = useMemo(() => {
    return (drift.server_comparisons || [])
      .filter((comparison) => comparison.is_outlier)
      .map((comparison) => comparison.server_id);
  }, [drift.server_comparisons]);

  const selectedServer = useMemo(() => {
    return (
      servers.find((server) => server.id === selectedServerId) ||
      servers.find((server) => peerDriftIds.includes(server.id)) ||
      servers[0] ||
      null
    );
  }, [servers, selectedServerId, peerDriftIds]);

  const totalServers = servers.length;
  const driftedCount = peerDriftIds.length;
  const healthyCount = Math.max(0, totalServers - driftedCount);

  const pageTitles = {
    "/dashboard": "Dashboard",
    "/servers": "Servers",
    "/comparisons": "Comparisons",
    "/baseline": "Baseline Management",
    "/history": "Drift History",
    "/ai-insights": "AI Insights",
    "/settings": "Settings",
  };

  const currentPage = pageTitles[currentPath] || "Dashboard";

  const handleRefresh = async () => {
    setMessage("");
    await reload();
  };

  const handleSimulate = async () => {
    try {
      setBusy(true);
      setMessage("");

      await postJson("/simulate-drift", {});
      await reload();

      setMessage("Drift simulation completed successfully.");
    } catch (err) {
      setMessage(err.message || "Unable to simulate drift.");
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    const confirmed = window.confirm(
      "Reset the demo fleet to its original configuration? Your approved baseline will not be changed."
    );

    if (!confirmed) return;

    try {
      setBusy(true);
      setMessage("");

      await postJson("/demo/reset", {});
      setSelectedServerId(null);
      await reload();

      setMessage(
        "Demo fleet reset successfully. Approved baseline preserved."
      );
    } catch (err) {
      setMessage(err.message || "Unable to reset the demo.");
    } finally {
      setBusy(false);
    }
  };

  const handleBaselineChange = async () => {
    await reload();
  };

  const renderMajorityComparison = () => {
    const majority = drift.majority || {};

    return (
      <section className="majority-summary">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PEER COMPARISON</p>
            <h2>Majority Configuration</h2>
          </div>

          <span className="info-chip">
            {majority.count || 0} / {majority.total_servers || totalServers} servers
          </span>
        </div>

        <p className="majority-description">
          This configuration represents the most common configuration
          detected across the fleet. It is used for peer comparison only;
          it is not automatically considered correct.
        </p>

        <div className="majority-grid">
          <div>
            <span>Majority percentage</span>
            <strong>
              {majority.percentage != null
                ? `${Number(majority.percentage).toFixed(1)}%`
                : "N/A"}
            </strong>
          </div>

          <div>
            <span>Servers in majority</span>
            <strong>{majority.count || 0}</strong>
          </div>

          <div>
            <span>Strict majority</span>
            <strong>{majority.has_majority ? "Yes" : "No"}</strong>
          </div>
        </div>
      </section>
    );
  };

  const renderBaselineVerification = () => {
    const majorityBaseline = drift.majority_vs_baseline || {};

    return (
      <section className="baseline-summary">
        <div className="section-heading">
          <div>
            <p className="eyebrow">SOURCE OF TRUTH</p>
            <h2>Approved Baseline Verification</h2>
          </div>

          <span
            className={`status-chip ${
              majorityBaseline.status === "compliant"
                ? "status-good"
                : majorityBaseline.status === "not_configured"
                ? "status-warning"
                : "status-bad"
            }`}
          >
            {majorityBaseline.status === "compliant"
              ? "Compliant"
              : majorityBaseline.status === "deviates"
              ? "Majority deviates"
              : "Baseline not configured"}
          </span>
        </div>

        <p className="majority-description">
          The majority configuration is checked independently against
          the original approved baseline. A majority configuration can
          still be incorrect if it differs from the approved baseline.
        </p>

        {majorityBaseline.status === "deviates" && (
          <div className="baseline-warning">
            Warning: The majority configuration differs from the
            approved baseline. Review these changes before treating
            them as acceptable.
          </div>
        )}

        {majorityBaseline.status === "not_configured" && (
          <div className="baseline-warning">
            No approved baseline has been configured yet. Capture an
            approved configuration before relying on baseline verification.
          </div>
        )}

        {majorityBaseline.status === "compliant" && (
          <div className="status-chip status-good">
            The majority configuration matches the approved baseline.
          </div>
        )}
      </section>
    );
  };

  const DashboardPage = () => (
    <>
      <section className="welcome-section">
        <div>
          <p className="eyebrow">CONFIGURATION MONITORING</p>
          <h1>Fleet Dashboard</h1>
          <p>
            Monitor server configurations, detect drift, and verify
            changes against your approved baseline.
          </p>
        </div>

        <div className="live-indicator">
          <span />
          Live monitoring
        </div>
      </section>

      <Overview
        total={totalServers}
        healthy={healthyCount}
        drifted={driftedCount}
        servers={servers}
        drift={drift}
      />
    </>
  );

  const ServersPage = () => (
    <>
      <section className="welcome-section">
        <div>
          <p className="eyebrow">FLEET MANAGEMENT</p>
          <h1>Server Monitoring</h1>
          <p>
            View individual servers, inspect their configurations,
            and investigate detected drift.
          </p>
        </div>
      </section>

      <div className="server-detail-layout">
        <div className="server-section">
          <ServerList
            servers={servers}
            outlierIds={peerDriftIds}
            selectedId={selectedServer?.id}
            onSelect={(server) => setSelectedServerId(server.id)}
          />
        </div>

        <div className="detail-section">
          <DetailPanel
            server={selectedServer}
            selectedServer={selectedServer}
            onRefresh={reload}
          />
        </div>
      </div>
    </>
  );

  const ComparisonsPage = () => (
    <>
      <section className="welcome-section">
        <div>
          <p className="eyebrow">CONFIGURATION ANALYSIS</p>
          <h1>Drift Comparisons</h1>
          <p>
            Compare the fleet majority against individual servers
            and the original approved baseline.
          </p>
        </div>
      </section>

      {renderMajorityComparison()}
      {renderBaselineVerification()}
    </>
  );

  const BaselinePage = () => (
    <>
      <section className="welcome-section">
        <div>
          <p className="eyebrow">SOURCE OF TRUTH</p>
          <h1>Baseline Management</h1>
          <p>
            Capture, review, and manage your original approved
            server configuration.
          </p>
        </div>
      </section>

      <BaselineManager onBaselineChange={handleBaselineChange} />
    </>
  );

  const renderCurrentPage = () => {
    switch (currentPath) {
      case "/dashboard":
        return <DashboardPage />;

      case "/servers":
        return <ServersPage />;

      case "/comparisons":
        return <ComparisonsPage />;

      case "/baseline":
        return <BaselinePage />;

      case "/history":
        return <DriftHistory />;

      case "/ai-insights":
        return <AIInsights servers={servers} drift={drift} />;

      case "/settings":
        return <SettingsPage />;

      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">C</div>

          <div>
            <h2>Configo</h2>
            <span>SERVER DRIFT DETECTOR</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <NavLink
            to="/dashboard"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span>▦</span>
            Dashboard
          </NavLink>

          <NavLink
            to="/servers"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span>▣</span>
            Servers
          </NavLink>

          <NavLink
            to="/comparisons"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span>⇄</span>
            Comparisons
          </NavLink>

          <NavLink
            to="/baseline"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span>◈</span>
            Baseline
          </NavLink>

          <div className="sidebar-nav-divider" />

          <p className="sidebar-group-label">ANALYSIS</p>

          <NavLink
            to="/history"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span>◷</span>
            Drift History
          </NavLink>

          <NavLink
            to="/ai-insights"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span>✧</span>
            AI Insights
          </NavLink>

          <div className="sidebar-nav-divider" />

          <p className="sidebar-group-label">MANAGEMENT</p>

          <NavLink
            to="/settings"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span>⚙</span>
            Settings
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <span className="sidebar-status-dot" />
          Fleet monitoring active
        </div>
      </aside>

      <main className="main-content">
        <Header
          updatedAt={updatedAt}
          onRefresh={handleRefresh}
          onSimulate={handleSimulate}
          onReset={handleReset}
          loading={loading}
          busy={busy}
        />

        <div className="dashboard-content">
          <div className="page-title-bar">
            <span>{currentPage}</span>
          </div>

          {message && (
            <div className="action-message" role="status">
              {message}
            </div>
          )}

          {error && (
            <div className="error-message" role="alert">
              {error}
            </div>
          )}

          {loading && currentPath !== "/settings" ? (
            <div className="detail-loading">Loading Configo data...</div>
          ) : (
            renderCurrentPage()
          )}
        </div>
      </main>
    </div>
  );
}

// --------------------------------------------------
// APP ENTRY POINT
// --------------------------------------------------

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<DashboardLayout />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
