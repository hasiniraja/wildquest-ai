import { useEffect, useRef } from 'react'

const TIPS = [
  'Asking Gemma to craft your quest…',
  'Thinking about your surroundings…',
  'Finding the perfect steps for you…',
  'Checking for safe activities…',
  'Almost ready to touch grass…',
]

export default function LoadingScreen() {
  const tipRef = useRef(null)
  const indexRef = useRef(0)

  useEffect(() => {
    const el = tipRef.current
    if (!el) return
    el.textContent = TIPS[0]

    const id = setInterval(() => {
      indexRef.current = (indexRef.current + 1) % TIPS.length
      if (el) {
        el.style.opacity = '0'
        setTimeout(() => {
          el.textContent = TIPS[indexRef.current]
          el.style.opacity = '1'
        }, 300)
      }
    }, 2400)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 gap-8 animate-fade-up">
      {/* Animated leaf rings */}
      <div className="relative flex items-center justify-center w-36 h-36">
        <div className="absolute inset-0 rounded-full border-2 border-forest-600/30 animate-ping" style={{ animationDuration: '2s' }} />
        <div className="absolute inset-3 rounded-full border-2 border-forest-500/20 animate-ping" style={{ animationDuration: '2.5s', animationDelay: '0.5s' }} />
        <div className="text-6xl animate-bounce" style={{ animationDuration: '2s' }}>🌿</div>
      </div>

      <div className="text-center">
        <h2 className="text-2xl font-bold text-stone-100 mb-3">Crafting your quest</h2>
        <p
          ref={tipRef}
          className="text-stone-400 text-sm transition-opacity duration-300"
          style={{ opacity: 1 }}
        />
      </div>

      <p className="text-stone-600 text-xs text-center max-w-xs">
        Using a local Gemma model — this may take 10–30 seconds depending on your hardware.
      </p>
    </div>
  )
}
