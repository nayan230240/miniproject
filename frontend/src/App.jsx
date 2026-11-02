
import React, { useMemo, useState } from "react";
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
import { postJson } from "./api";
import useFleet from "./hooks/useFleet";
import "./App.css";

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

  const majority = drift.majority || {};
  const majorityBaseline = drift.majority_vs_baseline || {};

  const pageTitles = {
    "/dashboard": "Dashboard",
    "/servers": "Servers",
    "/comparisons": "Comparisons",
    "/baseline": "Baseline Management",
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

  // Majority configuration: peer comparison only.
  const renderMajorityComparison = () => (
    <section className="majority-summary">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PEER COMPARISON</p>
          <h2>Majority Configuration</h2>
        </div>

        <span className="info-chip">
          {majority.count || 0} /{" "}
          {majority.total_servers || totalServers} servers
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

  // Majority configuration: independent approved baseline verification.
  const renderBaselineVerification = () => (
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

  // PAGE 1: Dashboard
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

  // PAGE 2: Servers
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

  // PAGE 3: Comparisons
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

  // PAGE 4: Baseline Management
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

  // Render exactly ONE page according to the selected route.
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
            className={({ isActive }) =>
              `nav-item ${isActive ? "active" : ""}`
            }
          >
            <span>▦</span>
            Dashboard
          </NavLink>

          <NavLink
            to="/servers"
            className={({ isActive }) =>
              `nav-item ${isActive ? "active" : ""}`
            }
          >
            <span>▣</span>
            Servers
          </NavLink>

          <NavLink
            to="/comparisons"
            className={({ isActive }) =>
              `nav-item ${isActive ? "active" : ""}`
            }
          >
            <span>⇄</span>
            Comparisons
          </NavLink>

          <NavLink
            to="/baseline"
            className={({ isActive }) =>
              `nav-item ${isActive ? "active" : ""}`
            }
          >
            <span>◈</span>
            Baseline
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

          {loading ? (
            <div className="detail-loading">
              Loading Configo data...
            </div>
          ) : (
            renderCurrentPage()
          )}
        </div>
      </main>
    </div>
  );
}

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
