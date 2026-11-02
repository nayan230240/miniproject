
import React from "react";

function ServerList({
  servers = [],
  outlierIds = [],
  selectedId,
  onSelect,
}) {
  const isDrifted = (serverId) => outlierIds.includes(serverId);

  if (!servers.length) {
    return (
      <section className="server-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">SERVER FLEET</p>
            <h2>Monitored Servers</h2>
          </div>
        </div>

        <div className="server-empty">
          No servers found. Check whether your fleet containers are running.
        </div>
      </section>
    );
  }

  return (
    <section className="server-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SERVER FLEET</p>
          <h2>Monitored Servers</h2>
        </div>

        <span className="info-chip">{servers.length} servers</span>
      </div>

      <div className="server-list">
        {servers.map((server) => {
          const drifted = isDrifted(server.id);
          const selected = selectedId === server.id;

          return (
            <button
              type="button"
              key={server.id}
              className={`server-item ${selected ? "selected" : ""}`}
              onClick={() => onSelect?.(server)}
            >
              <div className="server-item-main">
                <div className={`server-avatar ${drifted ? "avatar-drifted" : ""}`}>
                  🖥️
                </div>

                <div className="server-info">
                  <strong>{server.name || `Server ${server.id}`}</strong>
                  <span>ID: {server.id}</span>
                </div>
              </div>

              <span className={`server-status ${drifted ? "server-drifted" : "server-healthy"}`}>
                <span className="server-status-dot" />
                {drifted ? "Drifted" : "Healthy"}
              </span>
            </button>
          );
        })}
      </div>

      <div className="server-list-legend">
        <span>
          <i className="legend-dot legend-green" />
          Healthy
        </span>
        <span>
          <i className="legend-dot legend-red" />
          Peer drift
        </span>
      </div>
    </section>
  );
}

export default ServerList;
