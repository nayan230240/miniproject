// Tiny helper around fetch().
// All backend URLs start with VITE_API_URL (see docker-compose) or localhost:8000.

export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function parseError(path, response) {
  let detail = `${path} failed with HTTP ${response.status}`;

  try {
    const body = await response.json();

    if (body.detail) {
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    }
  } catch {
    // Keep the generic message if the body is not JSON.
  }

  return new Error(detail);
}

export async function getJson(path) {
  const response = await fetch(`${API_URL}${path}`);

  if (!response.ok) {
    throw await parseError(path, response);
  }

  return response.json();
}

export async function postJson(path, payload = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await parseError(path, response);
  }

  return response.json();
}

export async function putJson(path, payload = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await parseError(path, response);
  }

  return response.json();
}