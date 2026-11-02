
import React from "react";

function Overview({
  total = 0,
  healthy = 0,
  drifted = 0,
  servers = [],
}) {
  const stats = [
    {
      title: "Total Servers",
      value: total,
      description: "Servers monitored",
      icon: "🖥️",
      color: "blue",
    },
    {
      title: "Healthy Servers",
      value: healthy,
      description: "Matching the majority",
      icon: "✓",
      color: "green",
    },
    {
      title: "Drifted Servers",
      value: drifted,
      description: "Different from majority",
      icon: "⚠",
      color: "red",
    },
  ];

  return (
    <section className="overview-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">FLEET OVERVIEW</p>
          <h2>Configuration Health</h2>
        </div>

        <span className="info-chip">
          {servers.length} servers monitored
        </span>
      </div>

      <div className="overview-grid">
        {stats.map((stat) => (
          <article
            className={`overview-card overview-${stat.color}`}
            key={stat.title}
          >
            <div className="overview-card-top">
              <span className="overview-icon">{stat.icon}</span>
              <span className="overview-label">{stat.title}</span>
            </div>

            <div className="overview-value">{stat.value}</div>

            <p className="overview-description">
              {stat.description}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

export default Overview;
