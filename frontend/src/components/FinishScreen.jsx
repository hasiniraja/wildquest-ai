import { useState } from 'react'
import { saveEntry } from '../journal.js'
import SourceBadge from './SourceBadge.jsx'

const MOODS = [
  { value: 1, emoji: '😔', label: 'Low' },
  { value: 2, emoji: '😐', label: 'Meh' },
  { value: 3, emoji: '🙂', label: 'Good' },
  { value: 4, emoji: '😊', label: 'Great' },
  { value: 5, emoji: '🤩', label: 'Amazing' },
]

export default function FinishScreen({ questResponse, onNewQuest, onOpenJournal }) {
  const { quest, source, model, latency_ms, attempts } = questResponse
  const [notes, setNotes] = useState('')
  const [mood, setMood] = useState(null)
  const [saved, setSaved] = useState(false)

  function handleSave() {
    if (!mood) return
    saveEntry(questResponse, notes, mood)
    setSaved(true)
  }

  return (
    <div className="flex-1 flex flex-col px-5 pb-10 gap-6 animate-fade-up max-w-lg mx-auto w-full">
      {/* Hero */}
      <div className="text-center pt-4">
        <div className="text-5xl mb-3">🎉</div>
        <h1 className="text-3xl font-extrabold text-stone-100">Quest complete!</h1>
        <p className="text-stone-400 text-sm mt-1">{quest.title}</p>
        <div className="flex justify-center mt-2">
          <SourceBadge source={source} model={model} latency_ms={latency_ms} attempts={attempts} />
        </div>
      </div>

      {saved ? (
        /* ── Post-save state ── */
        <div className="flex flex-col gap-4 animate-fade-up">
          <div className="card text-center">
            <div className="text-3xl mb-2">✅</div>
            <p className="text-stone-300 font-semibold">Saved to your journal!</p>
            <p className="text-stone-500 text-sm mt-1">Great adventure today 🌿</p>
          </div>
          <button onClick={onOpenJournal} className="btn-secondary">
            📓 View journal
          </button>
          <button onClick={onNewQuest} className="btn-primary">
            Start a new quest
          </button>
        </div>
      ) : (
        /* ── Reflection form ── */
        <>
          {/* Notes */}
          <section className="flex flex-col gap-2">
            <label className="section-label" htmlFor="quest-notes">
              What did you notice?
            </label>
            <textarea
              id="quest-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="A bird landed near me. The leaves smelled earthy after rain…"
              rows={4}
              className="w-full rounded-2xl bg-stone-900 border border-stone-700 text-stone-100
                         placeholder-stone-600 px-4 py-3 text-sm resize-none
                         focus:outline-none focus:ring-2 focus:ring-forest-500 focus:border-transparent"
            />
          </section>

          {/* Mood */}
          <section>
            <p className="section-label">How do you feel?</p>
            <div className="flex gap-2">
              {MOODS.map((m) => (
                <button
                  key={m.value}
                  onClick={() => setMood(m.value)}
                  className={`flex-1 flex flex-col items-center gap-1 py-3 rounded-2xl border-2 transition-all duration-150 active:scale-95
                    ${mood === m.value
                      ? 'border-forest-500 bg-forest-900'
                      : 'border-stone-700 bg-stone-900'
                    }`}
                  aria-label={m.label}
                >
                  <span className="text-2xl">{m.emoji}</span>
                  <span className="text-xs text-stone-500">{m.label}</span>
                </button>
              ))}
            </div>
          </section>

          <button
            onClick={handleSave}
            disabled={!mood}
            className="btn-primary"
          >
            Save to journal 📓
          </button>

          <button
            onClick={onNewQuest}
            className="text-stone-500 hover:text-stone-300 text-sm text-center transition-colors"
          >
            Skip — start a new quest
          </button>
        </>
      )}
    </div>
  )
}
