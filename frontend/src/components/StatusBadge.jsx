// Colored pill: healthy (cyan) vs drifted (violet).

export default function StatusBadge({ drifted }) {
  return (
    <span className={`badge ${drifted ? "badge-drift" : "badge-ok"}`}>
      {drifted ? "Drifted" : "Healthy"}
    </span>
  );
}
