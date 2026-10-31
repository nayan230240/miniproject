// Three count cards at the top of the dashboard.

export default function Overview({ total, healthy, drifted }) {
  const cards = [
    { label: "Fleet size", value: total, tone: "neutral" },
    { label: "Healthy", value: healthy, tone: "ok" },
    { label: "Drifted", value: drifted, tone: "drift" },
  ];

  return (
    <section className="overview" aria-label="Fleet overview">
      {cards.map((card) => (
        <article key={card.label} className={`stat-card stat-${card.tone}`}>
          <p className="stat-label">{card.label}</p>
          <p className="stat-value">{card.value}</p>
        </article>
      ))}
    </section>
  );
}
