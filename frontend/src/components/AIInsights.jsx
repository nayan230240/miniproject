
import React, { useEffect, useMemo, useState } from "react";
import { getJson } from "../api";
import AiExplanation from "./AiExplanation";

function formatValue(value) {
  if (value === undefined || value === null) return "Not available";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function AIInsights({ servers = [], drift = {} }) {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const comparisons = drift.server_comparisons || [];
  const majorityBaseline = drift.majority_vs_baseline || {};

  const affectedComparisons = useMemo(() => {
    return comparisons.filter((item) => {
      return (
        item.is_outlier ||
        (item.baseline_differences || []).length > 0
      );
    });
  }, [comparisons]);

  const affectedIds = affectedComparisons
    .map((item) => item.server_id)
    .sort((a, b) => a - b)
    .join(",");

  useEffect(() => {
    let cancelled = false;

    async function loadInsights() {
      setLoading(true);
      setError("");
      setAnalyses([]);

      try {
        const results = await Promise.all(
          affectedComparisons.map(async (comparison) => {
            try {
              const result = await getJson(
                `/drift/${comparison.server_id}/explanation`
              );

              const server = servers.find(
                (item) => item.id === comparison.server_id
              );

              return {
                serverId: comparison.server_id,
                serverName:
                  server?.name || `Server ${comparison.server_id}`,
                result,
                error: "",
              };
            } catch (err) {
              return {
                serverId: comparison.server_id,
                serverName: `Server ${comparison.server_id}`,
                result: null,
                error: err.message || "Unable to load AI analysis.",
              };
            }
          })
        );

        if (!cancelled) {
          setAnalyses(results);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load AI insights.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadInsights();

    return () => {
      cancelled = true;
    };
  }, [affectedIds, servers]);

  const totalServers = servers.length;
  const affectedServers = affectedComparisons.length;
  const majorityStatus = majorityBaseline.status || "not_configured";

  const categoryCounts = useMemo(() => {
    const counts = {};

    affectedComparisons.forEach((comparison) => {
      const differences = [
        ...(comparison.differing_categories || []),
        ...(comparison.baseline_differences || []),
      ];

      differences.forEach((item) => {
        counts[item.category] = (counts[item.category] || 0) + 1;
      });
    });

    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [affectedComparisons]);

  return (
    <div className="ai-insights-page">
      <section className="welcome-section">
        <div>
          <p className="eyebrow">INTELLIGENT FLEET ANALYSIS</p>
          <h1>AI Insights</h1>
          <p>
            Understand configuration drift, identify potential risks,
            and review Gemini-powered recommendations.
          </p>
        </div>
        <span className="info-chip">Gemini AI Analysis</span>
      </section>

      <div className="ai-insight-stats">
        <div className="ai-insight-stat">
          <span>Total servers</span>
          <strong>{totalServers}</strong>
        </div>

        <div className="ai-insight-stat">
          <span>Affected servers</span>
          <strong>{affectedServers}</strong>
        </div>

        <div className="ai-insight-stat">
          <span>Unaffected servers</span>
          <strong>{Math.max(0, totalServers - affectedServers)}</strong>
        </div>

        <div className="ai-insight-stat">
          <span>Changed categories</span>
          <strong>{categoryCounts.length}</strong>
        </div>
      </div>

      <section className="ai-insight-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">BASELINE VERIFICATION</p>
            <h2>Fleet Majority Assessment</h2>
          </div>

          <span
            className={`status-chip ${
              majorityStatus === "compliant"
                ? "status-good"
                : majorityStatus === "not_configured"
                ? "status-warning"
                : "status-bad"
            }`}
          >
            {majorityStatus === "compliant"
              ? "Compliant"
              : majorityStatus === "deviates"
              ? "Deviates from baseline"
              : "Baseline not configured"}
          </span>
        </div>

        <p>
          {majorityStatus === "compliant"
            ? "The majority configuration matches the approved baseline."
            : majorityStatus === "deviates"
            ? "The most common fleet configuration differs from the approved baseline. Do not assume that the majority configuration is correct."
            : "Capture an approved baseline to verify whether the fleet configuration is compliant."}
        </p>

        {majorityStatus === "deviates" &&
          (majorityBaseline.differing_categories || []).length > 0 && (
            <div className="ai-category-list">
              {majorityBaseline.differing_categories.map((item, index) => (
                <div className="ai-category-item" key={`${item.category}-${index}`}>
                  <strong>{item.category}</strong>
                  <div>
                    <span>Approved baseline</span>
                    <code>{formatValue(item.baseline_value)}</code>
                  </div>
                  <div>
                    <span>Majority value</span>
                    <code>{formatValue(item.current_value)}</code>
                  </div>
                </div>
              ))}
            </div>
          )}
      </section>

      <section className="ai-insight-card">
        <p className="eyebrow">DRIFT PATTERNS</p>
        <h2>Frequently Affected Categories</h2>

        {categoryCounts.length === 0 ? (
          <p>No configuration differences are currently detected.</p>
        ) : (
          <div className="ai-category-list">
            {categoryCounts.map(([category, count]) => (
              <div className="ai-category-row" key={category}>
                <strong>{category}</strong>
                <span>{count} finding(s)</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="ai-insight-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">AI RECOMMENDATIONS</p>
            <h2>Gemini Server Analysis</h2>
          </div>

          <span className="info-chip">
            {analyses.length} analysis result(s)
          </span>
        </div>

        {loading && (
          <div className="detail-loading">
            Generating AI insights for affected servers...
          </div>
        )}

        {error && (
          <div className="error-message" role="alert">
            {error}
          </div>
        )}

        {!loading && affectedComparisons.length === 0 && (
          <div className="no-differences">
            No affected servers currently require AI analysis.
          </div>
        )}

        {!loading &&
          analyses.map((analysis) => (
            <div className="ai-server-analysis" key={analysis.serverId}>
              <h3>{analysis.serverName}</h3>

              {analysis.error ? (
                <div className="error-message">{analysis.error}</div>
              ) : (
                <AiExplanation
                  explanation={analysis.result?.explanation || {}}
                  source={analysis.result?.source}
                  fallbackReason={analysis.result?.fallback_reason}
                />
              )}
            </div>
          ))}
      </section>

      <p className="ai-insight-note">
        AI recommendations are advisory. Engineers must review findings
        against the approved baseline and make the final decision.
      </p>
    </div>
  );
}

export default AIInsights;
