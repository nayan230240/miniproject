// Three-part AI (or fallback) narration from GET /drift/{id}/explanation.

export default function AiExplanation({ payload, loading, error }) {
  if (loading) {
    return <p className="empty">Asking the narrator…</p>;
  }
  if (error) {
    return <p className="empty">Could not load explanation: {error}</p>;
  }
  if (!payload) {
    return <p className="empty">Select a server to read the AI summary.</p>;
  }

  const { explanation, source, fallback_reason: reason } = payload;
  const sourceLabel =
    source === "llm" ? "Live LLM" : source === "local" ? "Local (no drift)" : "Fallback (no API key or LLM error)";

  return (
    <div className="explain">
      <p className="source-chip">
        {sourceLabel}
        {reason ? ` · ${reason}` : ""}
      </p>
      <section>
        <h3>What changed</h3>
        <p>{explanation.what_changed}</p>
      </section>
      <section>
        <h3>Why it matters</h3>
        <p>{explanation.why_it_matters}</p>
      </section>
      <section>
        <h3>What to do next</h3>
        <p>{explanation.what_to_do_next}</p>
      </section>
    </div>
  );
}
