// Right-hand panel: diffs for the selected host + the AI explanation.
// The explanation is fetched whenever the selected server changes.

import { useEffect, useState } from "react";
import { getJson } from "../api.js";
import CategoryDiff from "./CategoryDiff.jsx";
import AiExplanation from "./AiExplanation.jsx";
import StatusBadge from "./StatusBadge.jsx";

export default function DetailPanel({ server, outlier }) {
  const [explanation, setExplanation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!server) {
      setExplanation(null);
      return;
    }
    let cancelled = false;
    setExplanation(null);
    setLoading(true);
    setError(null);
    getJson(`/drift/${server.id}/explanation`)
      .then((data) => {
        if (!cancelled) setExplanation(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [server]);

  if (!server) {
    return (
      <section className="panel detail-panel">
        <h2>Detail</h2>
        <p className="empty">Pick a server on the left to inspect drift.</p>
      </section>
    );
  }

  const drifted = Boolean(outlier);
  const diffs = outlier?.differing_categories || explanation?.differing_categories || [];

  return (
    <section className="panel detail-panel">
      <div className="detail-head">
        <div>
          <h2>{server.name}</h2>
          <p className="server-url">{server.base_url}</p>
        </div>
        <StatusBadge drifted={drifted} />
      </div>

      <h3 className="section-label">What changed</h3>
      <CategoryDiff diffs={diffs} />

      <h3 className="section-label">AI explanation</h3>
      <AiExplanation payload={explanation} loading={loading} error={error} />
    </section>
  );
}
