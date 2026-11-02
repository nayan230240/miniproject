
import React from "react";

export default function AiExplanation({
  explanation,
  source,
  fallbackReason,
  loading = false,
  error = null,
}) {
  if (loading) {
    return (
      <div style={styles.card}>
        <h3 style={styles.heading}>Gemini AI Explanation</h3>
        <p style={styles.muted}>
          Analyzing server configuration and detecting risks...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.card}>
        <h3 style={styles.heading}>Gemini AI Explanation</h3>
        <p style={styles.error}>{error}</p>
      </div>
    );
  }

  if (!explanation) {
    return (
      <div style={styles.card}>
        <h3 style={styles.heading}>Gemini AI Explanation</h3>
        <p style={styles.muted}>
          Select a server to view its AI explanation.
        </p>
      </div>
    );
  }

  const actualSource =
    source || explanation.source || "local";

  const actualFallbackReason =
    fallbackReason || explanation.fallback_reason;

  const isGemini = actualSource === "gemini";

  const sections = [
    {
      title: "What Changed?",
      description: explanation.what_changed,
      color: "#2563eb",
      background: "#eff6ff",
    },
    {
      title: "Why It Matters?",
      description: explanation.why_it_matters,
      color: "#d97706",
      background: "#fffbeb",
    },
    {
      title: "What To Do Next?",
      description: explanation.what_to_do_next,
      color: "#059669",
      background: "#ecfdf5",
    },
  ];

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div>
          <h3 style={styles.heading}>
            Gemini AI Explanation
          </h3>

          <p style={styles.subtitle}>
            AI-powered server drift analysis
          </p>
        </div>

        <span
          style={{
            ...styles.sourceBadge,
            background: isGemini ? "#dcfce7" : "#fef3c7",
            color: isGemini ? "#166534" : "#92400e",
          }}
        >
          {isGemini ? "Gemini AI" : "Fallback"}
        </span>
      </div>

      <div style={styles.sections}>
        {sections.map((section) => (
          <div
            key={section.title}
            style={{
              ...styles.section,
              background: section.background,
              borderLeft: `4px solid ${section.color}`,
            }}
          >
            <h4
              style={{
                ...styles.sectionTitle,
                color: section.color,
              }}
            >
              {section.title}
            </h4>

            <p style={styles.description}>
              {section.description ||
                "No information available."}
            </p>
          </div>
        ))}
      </div>

      {actualFallbackReason && (
        <p style={styles.fallbackNote}>
          Fallback reason: {actualFallbackReason}
        </p>
      )}
    </div>
  );
}

const styles = {
  card: {
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: "14px",
    padding: "22px",
    marginTop: "18px",
    boxShadow: "0 3px 12px rgba(15, 23, 42, 0.04)",
    color: "#1e293b",
  },

  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
    marginBottom: "20px",
  },

  heading: {
    margin: 0,
    fontSize: "19px",
    fontWeight: 700,
    color: "#172554",
  },

  subtitle: {
    margin: "6px 0 0",
    fontSize: "13px",
    color: "#64748b",
  },

  sourceBadge: {
    padding: "7px 12px",
    borderRadius: "20px",
    fontSize: "12px",
    fontWeight: 700,
  },

  sections: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: "14px",
  },

  section: {
    padding: "15px 17px",
    borderRadius: "9px",
  },

  sectionTitle: {
    margin: "0 0 9px",
    fontSize: "15px",
    fontWeight: 700,
  },

  description: {
    margin: 0,
    fontSize: "14px",
    lineHeight: 1.7,
    color: "#334155",
    whiteSpace: "pre-wrap",
  },

  muted: {
    color: "#64748b",
    fontSize: "14px",
  },

  error: {
    color: "#dc2626",
    fontSize: "14px",
  },

  fallbackNote: {
    marginTop: "16px",
    fontSize: "12px",
    color: "#92400e",
  },
};
