/** Backend base URL — set VITE_API_URL in frontend/.env when port 8000 is taken by another app. */
export const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env.VITE_API_URL) ||
  "http://localhost:8001";
