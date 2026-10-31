// DriftWise dashboard shell.
//
// Structure:
//   App            — fetches data, owns selected server
//   Header         — title + refresh
//   Overview       — healthy vs drifted counts
//   ServerList     — fleet rows + status badges
//   DetailPanel    — diffs + AI explanation (loads /drift/{id}/explanation)
//
// Data comes from GET /servers and GET /drift, refreshed every 30 seconds.

import { useEffect, useMemo, useState } from "react";
import Header from "./components/Header.jsx";
import Overview from "./components/Overview.jsx";
import ServerList from "./components/ServerList.jsx";
import DetailPanel from "./components/DetailPanel.jsx";
import { postJson } from "./api.js";
import { useFleet } from "./hooks/useFleet.js";
import "./App.css";

function App() {
  const { servers, drift, error, updatedAt, loading, reload } = useFleet();
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);

  const outlierById = useMemo(() => {
    const map = new Map();
    for (const item of drift?.outliers || []) {
      map.set(item.server_id, item);
    }
    return map;
  }, [drift]);

  const outlierIds = useMemo(() => new Set(outlierById.keys()), [outlierById]);

  // Prefer a drifted host on first load; keep the current selection after refresh.
  useEffect(() => {
    if (servers.length === 0) return;
    const stillThere = servers.some((server) => server.id === selectedId);
    if (stillThere) return;
    const firstDrifted = servers.find((server) => outlierIds.has(server.id));
    setSelectedId((firstDrifted || servers[0]).id);
  }, [servers, outlierIds, selectedId]);

  const selected = servers.find((server) => server.id === selectedId) || null;
  const healthy = servers.filter((server) => !outlierIds.has(server.id)).length;
  const drifted = outlierIds.size;

  async function simulateDrift() {
    setBusy(true);
    setActionError(null);
    try {
      const result = await postJson("/simulate-drift", { server_id: selectedId });
      await reload();
      if (result.server_id) setSelectedId(result.server_id);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function resetDemo() {
    setBusy(true);
    setActionError(null);
    try {
      await postJson("/demo/reset", {});
      await reload();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <Header
        updatedAt={updatedAt}
        onRefresh={reload}
        onSimulate={simulateDrift}
        onReset={resetDemo}
        loading={loading}
        busy={busy}
      />
      {error ? <p className="banner">{error}</p> : null}
      {actionError ? <p className="banner">{actionError}</p> : null}
      <Overview total={servers.length} healthy={healthy} drifted={drifted} />
      <div className="workspace">
        <ServerList
          servers={servers}
          selectedId={selectedId}
          onSelect={setSelectedId}
          outlierIds={outlierIds}
        />
        <DetailPanel server={selected} outlier={outlierById.get(selectedId) || null} />
      </div>
    </div>
  );
}

export default App;
