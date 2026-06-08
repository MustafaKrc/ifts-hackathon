const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";


async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `API request failed: ${response.status}`);
  }

  return response.json();
}

export function getHealth() {
  return request("/health");
}

export function getCustomerJourneys() {
  return request("/api/customer-journeys");
}

export function registerUser(payload) {
  return request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
