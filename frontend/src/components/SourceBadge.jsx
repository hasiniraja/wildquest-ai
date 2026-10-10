/**
 * SourceBadge — small pill showing whether the quest came from Gemma or fallback,
 * plus latency and attempt count.
 */
export default function SourceBadge({ source, model, latency_ms, attempts }) {
  const isGemma = source === 'gemma'

  return (
    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
          isGemma
            ? 'bg-forest-900 text-forest-400 border border-forest-700'
            : 'bg-stone-800 text-stone-400 border border-stone-700'
        }`}
      >
        {isGemma ? '✨ Gemma' : '📦 Fallback'}
      </span>
      {isGemma && (
        <>
          <span className="text-stone-700 text-xs">{latency_ms}ms</span>
          {attempts > 1 && (
            <span className="text-stone-700 text-xs">{attempts} attempts</span>
          )}
        </>
      )}
    </div>
  )
}
