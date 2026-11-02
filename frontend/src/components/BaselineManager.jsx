
import React, { useCallback, useEffect, useState } from "react";
import { getJson, postJson } from "../api";

function BaselineManager({ onBaselineChange }) {
  const [baseline, setBaseline] = useState(null);
  const [servers, setServers] = useState([]);
  const [selectedServerId, setSelectedServerId] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [baselineData, serverData] = await Promise.all([
        getJson("/baseline"),
        getJson("/servers"),
      ]);

      setBaseline(baselineData);
      setServers(serverData);

      if (serverData.length > 0) {
        setSelectedServerId((current) => {
          const exists = serverData.some(
            (server) => String(server.id) === current
          );

          return exists ? current : String(serverData[0].id);
        });
      }
    } catch (err) {
      setError(err.message || "Unable to load baseline information.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const selectedServer = servers.find(
    (server) => String(server.id) === selectedServerId
  );

  // IMPORTANT: The backend returns normalized_config as a JSON string.
  // Convert it into a JavaScript object before sending it back.
  const selectedConfig = (() => {
    const rawConfig =
      selectedServer?.latest_fingerprint?.normalized_config;

    if (!rawConfig) return null;

    try {
      const parsed =
        typeof rawConfig === "string"
          ? JSON.parse(rawConfig)
          : rawConfig;

      if (
        !parsed ||
        typeof parsed !== "object" ||
        Array.isArray(parsed)
      ) {
        return null;
      }

      return parsed;
    } catch {
      return null;
    }
  })();

  const handleCapture = async () => {
    if (!selectedConfig) {
      setError("No valid configuration is available for this server.");
      return;
    }

    const replacing = Boolean(baseline?.configured);

    const confirmationMessage = replacing
      ? "Are you sure you want to REPLACE the existing approved baseline? This changes your source of truth."
      : "Capture this server's current configuration as the original approved baseline?";

    if (!window.confirm(confirmationMessage)) return;

    try {
      setSaving(true);
      setError("");
      setMessage("");

      const result = await postJson("/baseline/capture", {
        config: selectedConfig,
        notes: notes.trim() || null,
        replace: replacing,
      });

      setBaseline(result.baseline);
      setNotes("");
      setMessage(result.message || "Baseline saved successfully.");

      await loadData();

      if (onBaselineChange) {
        await onBaselineChange();
      }
    } catch (err) {
      setError(err.message || "Unable to save the baseline.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!baseline?.configured) return;

    const confirmed = window.confirm(
      "Delete the approved baseline? Server fingerprints will remain."
    );

    if (!confirmed) return;

    try {
      setSaving(true);
      setError("");
      setMessage("");

      const response = await fetch("http://localhost:8000/baseline", {
        method: "DELETE",
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Unable to delete baseline.");
      }

      await loadData();

      setMessage("Approved baseline deleted.");

      if (onBaselineChange) {
        await onBaselineChange();
      }
    } catch (err) {
      setError(err.message || "Unable to delete the baseline.");
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (value) => {
    if (!value) return "Not available";
    return new Date(value).toLocaleString();
  };

  const formatValue = (value) => {
    if (value === null || value === undefined) {
      return "Not specified";
    }

    if (typeof value === "object") {
      return JSON.stringify(value, null, 2);
    }

    return String(value);
  };

  if (loading) {
    return (
      <div className="baseline-manager">
        Loading baseline information...
      </div>
    );
  }

  return (
    <section className="baseline-manager">
      <div className="baseline-manager-header">
        <div>
          <p className="eyebrow">SOURCE OF TRUTH</p>
          <h2>Baseline Management</h2>
          <p>
            Manage the original approved configuration used for
            server drift verification.
          </p>
        </div>

        <button
          className="baseline-manager-refresh"
          onClick={loadData}
          disabled={saving}
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      {message && (
        <div className="action-message" role="status">
          {message}
        </div>
      )}

      <div className="baseline-manager-card">
        <div className="baseline-manager-status">
          <div>
            <h3>Current Approved Baseline</h3>
            <p>
              {baseline?.configured
                ? "An approved baseline is currently stored."
                : "No approved baseline has been configured."}
            </p>
          </div>

          <span
            className={`status-chip ${
              baseline?.configured ? "status-good" : "status-warning"
            }`}
          >
            {baseline?.configured ? "Configured" : "Not configured"}
          </span>
        </div>

        {baseline?.configured && (
          <div className="baseline-manager-metadata">
            <div>
              <span>Created</span>
              <strong>{formatDate(baseline.created_at)}</strong>
            </div>

            <div>
              <span>Last updated</span>
              <strong>{formatDate(baseline.updated_at)}</strong>
            </div>

            <div>
              <span>Notes</span>
              <strong>{baseline.notes || "No notes added"}</strong>
            </div>
          </div>
        )}

        {baseline?.configured && baseline.config && (
          <div className="baseline-config">
            <h4>Approved Configuration</h4>

            {Object.entries(baseline.config).map(([category, value]) => (
              <div className="baseline-config-item" key={category}>
                <strong>{category.replaceAll("_", " ")}</strong>
                <pre>{formatValue(value)}</pre>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="baseline-manager-card">
        <h3>
          {baseline?.configured
            ? "Replace Approved Baseline"
            : "Capture Original Baseline"}
        </h3>

        <p>
          Select a server whose current configuration has been
          reviewed and explicitly approved by your engineering team.
        </p>

        <div className="baseline-form">
          <label htmlFor="baseline-server">Select source server</label>

          <select
            id="baseline-server"
            value={selectedServerId}
            onChange={(event) => setSelectedServerId(event.target.value)}
            disabled={saving || servers.length === 0}
          >
            {servers.map((server) => (
              <option key={server.id} value={String(server.id)}>
                {server.name}
              </option>
            ))}
          </select>

          <label htmlFor="baseline-notes">Approval notes</label>

          <textarea
            id="baseline-notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Example: Original configuration approved by the engineering team."
            rows={3}
            disabled={saving}
          />

          {!selectedConfig && (
            <p className="baseline-manager-warning">
              No valid configuration fingerprint is available for this server.
            </p>
          )}

          <button
            className="baseline-capture-button"
            onClick={handleCapture}
            disabled={saving || !selectedConfig}
          >
            {saving
              ? "Please wait..."
              : baseline?.configured
              ? "Replace Approved Baseline"
              : "Capture Approved Baseline"}
          </button>
        </div>
      </div>

      {baseline?.configured && (
        <div className="baseline-delete-section">
          <div>
            <h3>Delete Baseline</h3>
            <p>
              This removes the approved baseline but does not delete
              server fingerprints.
            </p>
          </div>

          <button
            className="baseline-delete-button"
            onClick={handleDelete}
            disabled={saving}
          >
            Delete Baseline
          </button>
        </div>
      )}
    </section>
  );
}

export default BaselineManager;

