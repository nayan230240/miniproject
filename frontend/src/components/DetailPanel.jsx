
import React, { useCallback, useEffect, useState } from "react";
import { getJson } from "../api";
import AiExplanation from "./AiExplanation";

function DetailPanel({ server, selectedServer, onRefresh }) {
  const activeServer = selectedServer || server;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [showAiSolution, setShowAiSolution] = useState(false);

  const loadAnalysis = useCallback(async () => {
    if (!activeServer?.id) {
      setData(null);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const result = await getJson(
        `/drift/${activeServer.id}/explanation`
      );

      setData(result);
    } catch (err) {
      setError(err.message || "Unable to load server analysis.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [activeServer?.id]);

  useEffect(() => {
    loadAnalysis();
  }, [loadAnalysis, refreshKey]);

  // Collapse the AI solution whenever a different server is selected.
  useEffect(() => {
    setShowAiSolution(false);
  }, [activeServer?.id]);

  const handleRefresh = async () => {
    if (onRefresh) {
      await onRefresh();
    }

    setRefreshKey((current) => current + 1);
  };

  const formatValue = (value) => {
    if (value === undefined || value === null) {
      return "Not available";
    }

    if (typeof value === "object") {
      return JSON.stringify(value, null, 2);
    }

    return String(value);
  };

  const renderDifferences = (differences, type) => {
    if (!differences || differences.length === 0) {
      return (
        <div className="no-differences">
          <span>✓</span>
          No differences detected in this comparison.
        </div>
      );
    }

    return (
      <div className="difference-list">
        {differences.map((item, index) => {
          let referenceValue;
          let currentValue;

          if (type === "majority") {
            referenceValue = item.majority_value;
            currentValue = item.server_value;
          } else {
            referenceValue = item.baseline_value;
            currentValue = item.current_value;
          }

          return (
            <div
              className="difference-item"
              key={`${item.category}-${index}`}
            >
              <div className="difference-category">
                {item.category}
              </div>

              <div className="difference-values">
                <div className="difference-value">
                  <span>
                    {type === "majority"
                      ? "Majority value"
                      : "Approved baseline"}
                  </span>
                  <code>{formatValue(referenceValue)}</code>
                </div>

                <div className="difference-value">
                  <span>
                    {type === "majority"
                      ? "Server value"
                      : "Current value"}
                  </span>
                  <code>{formatValue(currentValue)}</code>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  if (!activeServer) {
    return (
      <div className="detail-empty">
        <div className="detail-empty-icon">🖥️</div>
        <h3>No server selected</h3>
        <p>
          Select a server from the fleet list to inspect its configuration.
        </p>
      </div>
    );
  }

  const baselineStatus =
    data?.baseline_status ||
    data?.majority_vs_baseline?.status ||
    "not_configured";

  const statusLabels = {
    compliant: "Compliant with baseline",
    deviates: "Deviates from baseline",
    not_configured: "Baseline not configured",
    no_majority: "No strict majority",
  };

  const statusClass =
    baselineStatus === "compliant"
      ? "detail-status-good"
      : baselineStatus === "not_configured"
      ? "detail-status-warning"
      : "detail-status-danger";

  const explanation = data?.explanation || {};

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <div>
          <p className="eyebrow">SERVER INSPECTION</p>
          <h2>{activeServer.name || `Server ${activeServer.id}`}</h2>
          <p className="detail-subtitle">
            Detailed configuration comparison and AI analysis
          </p>
        </div>

        <button
          type="button"
          className="detail-refresh-button"
          onClick={handleRefresh}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "↻ Refresh Analysis"}
        </button>
      </div>

      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      <div className="detail-status-row">
        <span className="detail-status-label">
          Baseline verification
        </span>

        <span className={`detail-status ${statusClass}`}>
          {statusLabels[baselineStatus] || baselineStatus}
        </span>
      </div>

      {loading && !data ? (
        <div className="detail-loading">
          Loading configuration analysis...
        </div>
      ) : data ? (
        <>
          {/* Comparison 1: Server vs Majority */}
          <section className="comparison-card">
            <div className="comparison-heading">
              <span className="comparison-number">01</span>

              <div>
                <h3>Server vs Majority</h3>
                <p>
                  Identifies differences between this server and its peers.
                </p>
              </div>
            </div>

            {renderDifferences(data.differing_categories, "majority")}
          </section>

          {/* Comparison 2: Server vs Approved Baseline */}
          <section className="comparison-card">
            <div className="comparison-heading">
              <span className="comparison-number">02</span>

              <div>
                <h3>Server vs Approved Baseline</h3>
                <p>
                  Checks this server against the original approved
                  configuration.
                </p>
              </div>
            </div>

            {renderDifferences(data.baseline_differences, "baseline")}
          </section>

          {/* Comparison 3: Majority vs Approved Baseline */}
          <section className="comparison-card">
            <div className="comparison-heading">
              <span className="comparison-number">03</span>

              <div>
                <h3>Majority vs Approved Baseline</h3>
                <p>
                  Checks whether the most common fleet configuration
                  is itself compliant.
                </p>
              </div>
            </div>

            {data.majority_vs_baseline?.status === "not_configured" ? (
              <div className="no-differences">
                Approved baseline is not configured.
              </div>
            ) : (
              renderDifferences(
                data.majority_vs_baseline?.differing_categories,
                "baseline"
              )
            )}
          </section>

          {/* Collapsible Gemini AI Solution */}
          <section className="ai-analysis-section">
            <button
              type="button"
              className="ai-solution-toggle"
              onClick={() =>
                setShowAiSolution((current) => !current)
              }
              aria-expanded={showAiSolution}
            >
              <div className="comparison-heading">
                <span className="comparison-number ai-number">
                  AI
                </span>

                <div>
                  <h3>AI Solution</h3>
                  <p>
                    Gemini AI analysis and recommended actions.
                  </p>
                </div>
              </div>

              <span className="ai-toggle-icon">
                {showAiSolution ? "▲" : "▼"}
              </span>
            </button>

            {showAiSolution && (
              <div className="ai-solution-content">
                <AiExplanation
                  explanation={explanation}
                  source={data.source}
                  fallbackReason={data.fallback_reason}
                  loading={loading}
                  error={error}
                />
              </div>
            )}
          </section>
        </>
      ) : (
        <div className="detail-loading">
          No analysis data is currently available.
        </div>
      )}
    </div>
  );
}

export default DetailPanel;
