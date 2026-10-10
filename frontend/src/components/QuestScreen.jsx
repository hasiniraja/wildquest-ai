import { useState, useEffect, useCallback, useRef } from 'react'
import SourceBadge from './SourceBadge.jsx'

/**
 * QuestScreen — shows one step at a time, countdown timer, safety note.
 * Also contains "Phone Away" mode: near-black screen, timer only.
 */
export default function QuestScreen({ questResponse, onComplete }) {
  const { quest, source, model, latency_ms, attempts } = questResponse
  const totalSteps = quest.steps.length

  const [stepIndex, setStepIndex] = useState(0)
  const [phoneAway, setPhoneAway] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(quest.duration_minutes * 60)
  const [timerDone, setTimerDone] = useState(false)

  // ── Countdown timer ────────────────────────────────────────────────────────
  useEffect(() => {
    if (secondsLeft <= 0) {
      setTimerDone(true)
      return
    }
    const id = setTimeout(() => setSecondsLeft((s) => s - 1), 1000)
    return () => clearTimeout(id)
  }, [secondsLeft])

  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const progressPct = Math.round(((quest.duration_minutes * 60 - secondsLeft) / (quest.duration_minutes * 60)) * 100)

  // ── Step navigation ────────────────────────────────────────────────────────
  const goNext = useCallback(() => {
    if (stepIndex < totalSteps - 1) setStepIndex((i) => i + 1)
  }, [stepIndex, totalSteps])

  const goPrev = useCallback(() => {
    if (stepIndex > 0) setStepIndex((i) => i - 1)
  }, [stepIndex])

  // Swipe gesture support
  const touchStartX = useRef(null)
  function handleTouchStart(e) { touchStartX.current = e.touches[0].clientX }
  function handleTouchEnd(e) {
    if (touchStartX.current === null) return
    const dx = e.changedTouches[0].clientX - touchStartX.current
    if (Math.abs(dx) > 50) dx < 0 ? goNext() : goPrev()
    touchStartX.current = null
  }

  // ── Phone Away mode ────────────────────────────────────────────────────────
  if (phoneAway) {
    return (
      <div
        className="fixed inset-0 bg-black flex flex-col items-center justify-center cursor-pointer select-none"
        onClick={() => setPhoneAway(false)}
      >
        <div className="flex flex-col items-center gap-6 animate-pulse-ring">
          <div className="text-7xl font-mono font-bold text-stone-800 tabular-nums">
            {formatTime(secondsLeft)}
          </div>
          <p className="text-stone-700 text-sm">You've got this 🌿</p>
          <p className="text-stone-800 text-xs">Tap anywhere to return</p>
        </div>
      </div>
    )
  }

  // ── Main quest view ────────────────────────────────────────────────────────
  return (
    <div
      className="flex-1 flex flex-col min-h-0"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Header: timer + progress */}
      <div className="px-5 pt-3 pb-4 bg-forest-950 border-b border-stone-800">
        <div className="flex items-center justify-between mb-2">
          {/* Quest title */}
          <div>
            <h1 className="font-bold text-stone-100 text-base leading-tight line-clamp-1">
              {quest.title}
            </h1>
            <SourceBadge source={source} model={model} latency_ms={latency_ms} attempts={attempts} />
          </div>
          {/* Timer */}
          <div className={`text-2xl font-mono font-bold tabular-nums ${timerDone ? 'text-amber-400' : 'text-forest-400'}`}>
            {timerDone ? '✓ Done!' : formatTime(secondsLeft)}
          </div>
        </div>
        {/* Progress bar */}
        <div className="h-1.5 bg-stone-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-forest-500 rounded-full transition-all duration-1000"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-xs text-stone-600">Step {stepIndex + 1} of {totalSteps}</span>
          <span className="text-xs text-stone-600">{progressPct}% time used</span>
        </div>
      </div>

      {/* Step content — scrollable */}
      <div className="flex-1 overflow-y-auto px-5 py-6 flex flex-col gap-5">
        {/* Current step — large readable text */}
        <div className="card flex-1 flex flex-col justify-center animate-slide-in" key={stepIndex}>
          <p className="text-xs font-bold uppercase tracking-widest text-forest-500 mb-4">
            Step {stepIndex + 1}
          </p>
          <p className="text-2xl font-semibold text-stone-100 leading-snug">
            {quest.steps[stepIndex]}
          </p>
        </div>

        {/* Things to notice (shown from step 1 onward) */}
        {stepIndex >= 0 && quest.things_to_notice.length > 0 && (
          <div className="card">
            <p className="section-label">👀 Things to notice</p>
            <ul className="space-y-2">
              {quest.things_to_notice.map((t, i) => (
                <li key={i} className="flex items-start gap-2 text-stone-300 text-sm">
                  <span className="text-forest-500 mt-0.5">•</span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Screen-free tip */}
        <div className="card bg-stone-800/50">
          <p className="section-label">💡 Screen-free tip</p>
          <p className="text-stone-300 text-sm leading-relaxed">{quest.screen_free_tip}</p>
        </div>
      </div>

      {/* Bottom controls */}
      <div className="px-5 pt-3 pb-6 border-t border-stone-800 flex flex-col gap-3 bg-forest-950">
        {/* Safety note — always visible */}
        <div className="safety-bar">
          <span className="text-lg shrink-0">⚠️</span>
          <span>{quest.safety_note}</span>
        </div>

        {/* Step navigation */}
        <div className="flex gap-3">
          <button
            onClick={goPrev}
            disabled={stepIndex === 0}
            className="btn-secondary flex-1 py-3 text-base"
          >
            ← Back
          </button>

          {stepIndex < totalSteps - 1 ? (
            <button onClick={goNext} className="btn-primary flex-1 py-3 text-base">
              Next →
            </button>
          ) : (
            <button onClick={onComplete} className="btn-primary flex-1 py-3 text-base bg-amber-500 hover:bg-amber-400">
              Finish ✓
            </button>
          )}
        </div>

        {/* Phone Away button */}
        <button
          onClick={() => setPhoneAway(true)}
          className="text-stone-500 hover:text-stone-300 text-xs text-center py-1 transition-colors"
        >
          📵 Phone Away mode
        </button>
      </div>
    </div>
  )
}
