
import React, { useEffect, useState } from "react";
import { getJson } from "../api";

const CATEGORIES = [
  "os_version",
  "kernel_version",
  "installed_packages",
  "open_ports",
  "environment_variables",
  "ssh_settings",
];

const styles = {
  page: { display: "flex", flexDirection: "column", gap: "20px" },
  heading: { fontSize: "24px", fontWeight: 800, margin: 0 },
  subtitle: { color: "#64748b", fontSize: "13px", marginTop: "6px" },
  filters: {
    display: "flex", gap: "12px", flexWrap: "wrap",
    alignItems: "center", padding: "16px",
    background: "var(--card-bg, #fff)",
    border: "1px solid var(--border-color, #e2e8f0)",
    borderRadius: "12px",
  },
  select: {
    padding: "10px 12px", borderRadius: "8px",
    border: "1px solid #cbd5e1", background: "transparent",
    color: "inherit", minWidth: "180px",
  },
  card: {
    background: "var(--card-bg, #fff)",
    border: "1px solid var(--border-color, #e2e8f0)",
    borderRadius: "12px", padding: "18px",
  },
  badge: {
    display: "inline-block", padding: "4px 9px",
    borderRadius: "20px", fontSize: "11px",
    fontWeight: 700,
  },
  value: {
    padding: "10px", borderRadius: "7px",
    background: "var(--page-bg, #f8fafc)",
    fontSize: "12px", overflowWrap: "anywhere",
    whiteSpace: "pre-wrap",
  },
  button: {
    padding: "9px 15px", borderRadius: "8px",
    border: "1px solid #cbd5e1", background: "transparent",
    cursor: "pointer", color: "inherit",
  },
};

function formatValue(value) {
  if (value === undefined) return "Not available";
  if (value === null) return "null";

  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
}

function formatDate(value) {
  if (!value) return "Unknown time";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}

export default function DriftHistory() {
  const [events, setEvents] = useState([]);
  const [servers, setServers] = useState([]);
  const [totalEvents, setTotalEvents] = useState(0);

  const [serverId, setServerId] = useState("");
  const [category, setCategory] = useState("");

  const [offset, setOffset] = useState(0);
  const limit = 20;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      setLoading(true);
      setError("");

      try {
        const params = new URLSearchParams({
          limit: String(limit),
          offset: String(offset),
        });

        if (serverId) params.set("server_id", serverId);
        if (category) params.set("category", category);

        const [historyData, serverData] = await Promise.all([
          getJson(`/history?${params.toString()}`),
          getJson("/servers"),
        ]);

        if (cancelled) return;

        setEvents(historyData.events || []);
        setTotalEvents(historyData.total_events || 0);
        setServers(serverData || []);
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load drift history.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [serverId, category, offset]);

  function changeServer(value) {
    setServerId(value);
    setOffset(0);
  }

  function changeCategory(value) {
    setCategory(value);
    setOffset(0);
  }

  const hasPrevious = offset > 0;
  const hasNext = offset + limit < totalEvents;

  return (
    <div style={styles.page}>
      <div>
        <h2 style={styles.heading}>Drift History</h2>
        <p style={styles.subtitle}>
          Track configuration changes detected across your server fleet.
        </p>
      </div>

      <div style={styles.filters}>
        <select
          style={styles.select}
          value={serverId}
          onChange={(e) => changeServer(e.target.value)}
        >
          <option value="">All Servers</option>
          {servers.map((server) => (
            <option key={server.id} value={server.id}>
              {server.name}
            </option>
          ))}
        </select>

        <select
          style={styles.select}
          value={category}
          onChange={(e) => changeCategory(e.target.value)}
        >
          <option value="">All Categories</option>
          {CATEGORIES.map((item) => (
            <option key={item} value={item}>
              {item.replaceAll("_", " ")}
            </option>
          ))}
        </select>

        <button
          style={styles.button}
          onClick={() => {
            setOffset(0);
            setServerId("");
            setCategory("");
          }}
        >
          Clear Filters
        </button>
      </div>

      <div style={styles.card}>
        <div style={{ fontSize: "12px", color: "#64748b" }}>
          Total detected changes
        </div>
        <div style={{ fontSize: "28px", fontWeight: 800, marginTop: "5px" }}>
          {totalEvents}
        </div>
      </div>

      {loading && (
        <div style={styles.card}>Loading drift history...</div>
      )}

      {!loading && error && (
        <div style={{ ...styles.card, color: "#dc2626" }}>
          {error}
          <button
            style={{ ...styles.button, marginLeft: "12px" }}
            onClick={() => setOffset(0)}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && events.length === 0 && (
        <div style={styles.card}>
          <h3 style={{ marginTop: 0 }}>No configuration changes found</h3>
          <p style={{ color: "#64748b", fontSize: "13px" }}>
            Changes will appear here when the poller detects a difference
            between consecutive fingerprints.
          </p>
        </div>
      )}

      {!loading && !error && events.map((event) => {
        const reverted = event.event_type === "reverted";

        return (
          <div key={event.id} style={styles.card}>
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "12px",
              flexWrap: "wrap",
              alignItems: "center",
            }}>
              <div>
                <strong>{event.server_name}</strong>
                <div style={{
                  fontSize: "12px",
                  color: "#64748b",
                  marginTop: "5px",
                }}>
                  {event.category.replaceAll("_", " ")}
                </div>
              </div>

              <span style={{
                ...styles.badge,
                background: reverted ? "#dcfce7" : "#fef3c7",
                color: reverted ? "#166534" : "#92400e",
              }}>
                {reverted ? "REVERTED" : "CHANGED"}
              </span>
            </div>

            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "12px",
              marginTop: "18px",
            }}>
              <div>
                <div style={{
                  fontSize: "11px", fontWeight: 700,
                  color: "#64748b", marginBottom: "7px",
                }}>
                  PREVIOUS VALUE
                </div>
                <div style={styles.value}>
                  {formatValue(event.previous_value)}
                </div>
              </div>

              <div>
                <div style={{
                  fontSize: "11px", fontWeight: 700,
                  color: "#64748b", marginBottom: "7px",
                }}>
                  NEW VALUE
                </div>
                <div style={styles.value}>
                  {formatValue(event.new_value)}
                </div>
              </div>
            </div>

            <div style={{
              fontSize: "11px",
              color: "#64748b",
              marginTop: "15px",
            }}>
              Detected: {formatDate(event.detected_at)}
            </div>
          </div>
        );
      })}

      {!loading && !error && totalEvents > 0 && (
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
        }}>
          <span style={{ fontSize: "12px", color: "#64748b" }}>
            Showing {offset + 1}–{Math.min(offset + limit, totalEvents)}
            {" "}of {totalEvents}
          </span>

          <div style={{ display: "flex", gap: "8px" }}>
            <button
              style={styles.button}
              disabled={!hasPrevious}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              Previous
            </button>

            <button
              style={styles.button}
              disabled={!hasNext}
              onClick={() => setOffset(offset + limit)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
