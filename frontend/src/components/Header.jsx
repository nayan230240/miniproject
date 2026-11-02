
import React, { useEffect, useState } from "react";

function Header({
  updatedAt,
  onRefresh,
  onSimulate,
  onReset,
  loading = false,
  busy = false,
}) {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("configo-theme") || "light"
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("configo-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((current) => (current === "light" ? "dark" : "light"));
  };

  const formattedTime = updatedAt
    ? new Date(updatedAt).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Not available";

  return (
    <header className="top-header">
      <div className="header-left">
        <p className="header-eyebrow">CONFIGO / MONITORING</p>
        <h2>Server Configuration Monitor</h2>
        <span className="header-updated">
          Last updated: {formattedTime}
        </span>
      </div>

      <div className="header-actions">
        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
        >
          <span>{theme === "light" ? "🌙" : "☀️"}</span>
          {theme === "light" ? "Dark Mode" : "Light Mode"}
        </button>

        <button
          type="button"
          className="header-button reset-button"
          onClick={onReset}
          disabled={busy}
        >
          Reset Demo
        </button>

        <button
          type="button"
          className="header-button refresh-button"
          onClick={onRefresh}
          disabled={loading || busy}
        >
          {loading ? "Refreshing..." : "↻ Refresh"}
        </button>

        <button
          type="button"
          className="header-button simulate-button"
          onClick={onSimulate}
          disabled={busy}
        >
          {busy ? "Please wait..." : "+ Simulate Drift"}
        </button>
      </div>
    </header>
  );
}

export default Header;
