import { useState, useEffect } from 'react'
import { getEntries, exportJournal, deleteEntry } from '../journal.js'
import SourceBadge from './SourceBadge.jsx'

const MOOD_EMOJI = { 1: '😔', 2: '😐', 3: '🙂', 4: '😊', 5: '🤩' }

export default function JournalScreen() {
  const [entries, setEntries] = useState([])
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    setEntries(getEntries())
  }, [])

  function handleDelete(id) {
    deleteEntry(id)
    setEntries(getEntries())
    if (expanded === id) setExpanded(null)
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
    })
  }

  return (
    <div className="flex-1 flex flex-col px-5 pb-10 gap-4 animate-fade-up max-w-lg mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between pt-2">
        <div>
          <h1 className="text-2xl font-extrabold text-stone-100">Journal</h1>
          <p className="text-stone-500 text-xs">{entries.length} {entries.length === 1 ? 'quest' : 'quests'} logged</p>
        </div>
        {entries.length > 0 && (
          <button
            onClick={exportJournal}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-stone-800 border border-stone-700
                       text-stone-300 text-sm font-semibold active:scale-95 transition-all"
          >
            ⬇️ Export JSON
          </button>
        )}
      </div>

      {/* Empty state */}
      {entries.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center py-16">
          <div className="text-5xl">📓</div>
          <p className="text-stone-400 font-semibold">No quests yet</p>
          <p className="text-stone-600 text-sm">Complete a quest and save it to see it here.</p>
        </div>
      )}

      {/* Entry list */}
      <div className="flex flex-col gap-3">
        {entries.map((entry) => (
          <div key={entry.id} className="card flex flex-col gap-3">
            {/* Summary row */}
            <button
              className="flex items-start justify-between gap-3 text-left w-full"
              onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
              aria-expanded={expanded === entry.id}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-stone-100 text-base leading-tight">
                    {entry.quest.title}
                  </span>
                  {entry.mood && (
                    <span className="text-lg" title={`Mood: ${entry.mood}/5`}>
                      {MOOD_EMOJI[entry.mood]}
                    </span>
                  )}
                </div>
                <p className="text-stone-500 text-xs mt-0.5">{formatDate(entry.date)}</p>
                <div className="mt-1">
                  <SourceBadge
                    source={entry.source}
                    model={entry.model}
                    latency_ms={entry.latency_ms}
                    attempts={entry.attempts}
                  />
                </div>
              </div>
              <span className="text-stone-600 text-lg shrink-0 mt-0.5">
                {expanded === entry.id ? '▲' : '▼'}
              </span>
            </button>

            {/* Expanded detail */}
            {expanded === entry.id && (
              <div className="flex flex-col gap-3 border-t border-stone-800 pt-3 animate-fade-up">
                <p className="text-stone-400 text-sm leading-relaxed">{entry.quest.description}</p>

                {/* Steps */}
                <div>
                  <p className="section-label">Steps</p>
                  <ol className="space-y-1.5">
                    {entry.quest.steps.map((s, i) => (
                      <li key={i} className="flex gap-2 text-stone-300 text-sm">
                        <span className="text-forest-500 font-bold shrink-0">{i + 1}.</span>
                        {s}
                      </li>
                    ))}
                  </ol>
                </div>

                {/* Notes */}
                {entry.notes && (
                  <div>
                    <p className="section-label">Your notes</p>
                    <p className="text-stone-300 text-sm italic leading-relaxed">"{entry.notes}"</p>
                  </div>
                )}

                {/* Delete */}
                <button
                  onClick={() => handleDelete(entry.id)}
                  className="text-stone-600 hover:text-red-400 text-xs transition-colors text-left"
                >
                  🗑 Delete this entry
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
