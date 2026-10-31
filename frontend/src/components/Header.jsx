// Top bar: product name plus the two demo buttons.

export default function Header({
  updatedAt,
  onRefresh,
  onSimulate,
  onReset,
  loading,
  busy,
}) {
  const stamp = updatedAt
    ? updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "waiting for first poll";
  const disabled = loading || busy;

  return (
    <header className="header">
      <div>
        <p className="eyebrow">Configo</p>
        <h1>DriftWise</h1>
        <p className="subtitle">Fleet configuration drift, hashed and explained</p>
      </div>
      <div className="header-meta">
        <p className="refresh-stamp">Updated {stamp}</p>
        <div className="header-actions">
          <button type="button" className="ghost-btn" onClick={onReset} disabled={disabled}>
            Reset demo
          </button>
          <button type="button" className="ghost-btn" onClick={onRefresh} disabled={disabled}>
            {loading ? "Loading…" : "Refresh now"}
          </button>
          <button type="button" className="primary-btn" onClick={onSimulate} disabled={disabled}>
            {busy ? "Simulating…" : "Simulate drift"}
          </button>
        </div>
      </div>
    </header>
  );
}
