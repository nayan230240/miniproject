// Placeholder home screen. Real drift UI comes later.

import { useEffect, useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [health, setHealth] = useState("checking...");

  // Ping the backend /health route once when the page loads.
  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then((data) => setHealth(data.status || "unknown"))
      .catch(() => setHealth("backend not reachable yet"));
  }, []);

  return (
    <main className="page">
      <h1>Configo</h1>
      <p>AI-powered configuration drift detector</p>
      <p className="status">Backend health: {health}</p>
      <p className="hint">Features are not implemented yet. This is only the project scaffold.</p>
    </main>
  );
}

export default App;
