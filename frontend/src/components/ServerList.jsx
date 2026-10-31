// Clickable list of machines. The selected row opens the detail panel.

import StatusBadge from "./StatusBadge.jsx";

export default function ServerList({ servers, selectedId, onSelect, outlierIds }) {
  if (servers.length === 0) {
    return (
      <section className="panel">
        <h2>Servers</h2>
        <p className="empty">No hosts yet. The backend poller writes rows every 30 seconds.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>Servers</h2>
      <ul className="server-list">
        {servers.map((server) => {
          const drifted = outlierIds.has(server.id);
          const active = server.id === selectedId;
          return (
            <li key={server.id}>
              <button
                type="button"
                className={`server-row ${active ? "is-active" : ""}`}
                onClick={() => onSelect(server.id)}
              >
                <span>
                  <span className="server-name">{server.name}</span>
                  <span className="server-url">{server.base_url}</span>
                </span>
                <StatusBadge drifted={drifted} />
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
