/**
 * api.js — thin wrapper around the FastAPI backend.
 * Uses the Vite proxy (/api → localhost:8000) so no CORS issues in dev.
 */

const BASE = '/api'

/**
 * Generate a quest from the backend.
 * @param {Object} params - QuestRequest fields
 * @returns {Promise<Object>} QuestResponse
 */
export async function generateQuest(params) {
  const res = await fetch(`${BASE}/quest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Server error ${res.status}`)
  }
  return res.json()
}

/**
 * Health check — resolves with { status, ollama, available_models? }
 */
export async function healthCheck() {
  const res = await fetch(`${BASE}/health`)
  return res.json()
}
