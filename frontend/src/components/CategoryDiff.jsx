// Shows each drifted category: majority value vs this server's value.

function pretty(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export default function CategoryDiff({ diffs }) {
  if (!diffs || diffs.length === 0) {
    return <p className="empty">This host matches the majority fingerprint.</p>;
  }

  return (
    <div className="diff-list">
      {diffs.map((diff) => (
        <article key={diff.category} className="diff-card">
          <h3>{diff.category.replaceAll("_", " ")}</h3>
          <div className="diff-grid">
            <div>
              <p className="diff-label">Majority</p>
              <pre>{pretty(diff.majority_value)}</pre>
            </div>
            <div>
              <p className="diff-label">This server</p>
              <pre>{pretty(diff.server_value)}</pre>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
