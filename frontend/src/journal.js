/**
 * journal.js — localStorage journal helpers.
 * Entries never leave the device; no server calls.
 */

const KEY = 'wildquest_journal'

/** @returns {Array} all journal entries, newest first */
export function getEntries() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

/**
 * Save a finished quest to the journal.
 * @param {Object} questResponse  - full QuestResponse from the API
 * @param {string} notes          - user's "what did you notice?" text
 * @param {number} mood           - 1-5 rating
 */
export function saveEntry(questResponse, notes, mood) {
  const entries = getEntries()
  const entry = {
    id: Date.now(),
    date: new Date().toISOString(),
    quest: questResponse.quest,
    source: questResponse.source,
    model: questResponse.model,
    latency_ms: questResponse.latency_ms,
    attempts: questResponse.attempts,
    notes,
    mood,
  }
  entries.unshift(entry)
  localStorage.setItem(KEY, JSON.stringify(entries))
  return entry
}

/** Export all entries as a downloadable JSON file */
export function exportJournal() {
  const entries = getEntries()
  const blob = new Blob([JSON.stringify(entries, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `wildquest-journal-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

/** Delete a single entry by id */
export function deleteEntry(id) {
  const entries = getEntries().filter((e) => e.id !== id)
  localStorage.setItem(KEY, JSON.stringify(entries))
}
