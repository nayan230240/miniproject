
// Loads fleet + drift data and refreshes every 30 seconds.

import { useCallback, useEffect, useState } from "react";
import { getJson } from "../api.js";

const REFRESH_MS = 30_000;

function useFleet() {
  const [servers, setServers] = useState([]);
  const [drift, setDrift] = useState({});
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const [serverRows, driftRow] = await Promise.all([
        getJson("/servers"),
        getJson("/drift"),
      ]);

      setServers(serverRows);
      setDrift(driftRow);
      setError(null);
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err.message || "Could not reach the Configo API");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();

    const timer = setInterval(reload, REFRESH_MS);

    return () => clearInterval(timer);
  }, [reload]);

  return {
    servers,
    drift,
    error,
    updatedAt,
    loading,
    reload,
  };
}

export { useFleet };
export default useFleet;
