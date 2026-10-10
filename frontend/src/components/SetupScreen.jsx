import { useState } from 'react'

const DURATIONS = [10, 15, 20, 30, 45, 60]
const ENERGY_LEVELS = [
  { value: 'low',    label: '🧘 Low',    desc: 'Easy stroll' },
  { value: 'medium', label: '🚶 Medium', desc: 'Moderate pace' },
  { value: 'high',   label: '🏃 High',   desc: 'Active & brisk' },
]
const SETTINGS = [
  { value: 'park',     emoji: '🌳', label: 'Park' },
  { value: 'garden',   emoji: '🌸', label: 'Garden' },
  { value: 'street',   emoji: '🏙️', label: 'Street' },
  { value: 'trail',    emoji: '🥾', label: 'Trail' },
  { value: 'backyard', emoji: '🏡', label: 'Backyard' },
]
const INTERESTS = [
  { value: 'birds',    emoji: '🐦', label: 'Birds' },
  { value: 'plants',   emoji: '🌿', label: 'Plants' },
  { value: 'sounds',   emoji: '👂', label: 'Sounds' },
  { value: 'textures', emoji: '🪨', label: 'Textures' },
  { value: 'colors',   emoji: '🎨', label: 'Colors' },
  { value: 'insects',  emoji: '🐛', label: 'Insects' },
  { value: 'sky',      emoji: '☁️', label: 'Sky' },
]
const AGE_GROUPS = [
  { value: 'kids',   emoji: '🧒', label: 'Kids' },
  { value: 'teens',  emoji: '🧑', label: 'Teens' },
  { value: 'adults', emoji: '👤', label: 'Adults' },
]

export default function SetupScreen({ onSubmit }) {
  const [duration, setDuration] = useState(20)
  const [energy, setEnergy] = useState('medium')
  const [setting, setSetting] = useState('park')
  const [interests, setInterests] = useState(['plants'])
  const [ageGroup, setAgeGroup] = useState('adults')

  function toggleInterest(val) {
    setInterests((prev) => {
      if (prev.includes(val)) return prev.filter((i) => i !== val)
      if (prev.length >= 3) return prev // max 3
      return [...prev, val]
    })
  }

  function handleSubmit(e) {
    e.preventDefault()
    onSubmit({ duration_minutes: duration, energy_level: energy, setting, interests, age_group: ageGroup })
  }

  const canSubmit = interests.length >= 1

  return (
    <form onSubmit={handleSubmit} className="flex-1 flex flex-col px-5 pb-8 gap-6 animate-fade-up max-w-lg mx-auto w-full">
      <div className="pt-2">
        <h1 className="text-3xl font-extrabold text-stone-100 leading-tight">
          Plan your quest
        </h1>
        <p className="text-stone-400 text-sm mt-1">Get outside. Touch grass. 🌱</p>
      </div>

      {/* Duration */}
      <section>
        <p className="section-label">Duration</p>
        <div className="grid grid-cols-3 gap-2">
          {DURATIONS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDuration(d)}
              className={`chip ${duration === d ? 'chip-on' : 'chip-off'}`}
            >
              <span className="font-bold">{d}</span>
              <span className="text-xs opacity-70">min</span>
            </button>
          ))}
        </div>
      </section>

      {/* Energy */}
      <section>
        <p className="section-label">Energy level</p>
        <div className="flex flex-col gap-2">
          {ENERGY_LEVELS.map((e) => (
            <button
              key={e.value}
              type="button"
              onClick={() => setEnergy(e.value)}
              className={`chip justify-start gap-3 ${energy === e.value ? 'chip-on' : 'chip-off'}`}
            >
              <span className="text-lg">{e.label}</span>
              <span className="text-xs opacity-60 font-normal">{e.desc}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Setting */}
      <section>
        <p className="section-label">Where are you?</p>
        <div className="grid grid-cols-3 gap-2">
          {SETTINGS.map((s) => (
            <button
              key={s.value}
              type="button"
              onClick={() => setSetting(s.value)}
              className={`chip flex-col gap-1 py-4 ${setting === s.value ? 'chip-on' : 'chip-off'}`}
            >
              <span className="text-2xl">{s.emoji}</span>
              <span className="text-xs">{s.label}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Interests */}
      <section>
        <p className="section-label">
          Interests
          <span className="ml-2 text-stone-600 normal-case font-normal tracking-normal">
            pick up to 3 ({interests.length}/3)
          </span>
        </p>
        <div className="grid grid-cols-4 gap-2">
          {INTERESTS.map((i) => (
            <button
              key={i.value}
              type="button"
              onClick={() => toggleInterest(i.value)}
              disabled={!interests.includes(i.value) && interests.length >= 3}
              className={`chip flex-col gap-1 py-4 ${interests.includes(i.value) ? 'chip-on' : 'chip-off'} disabled:opacity-30`}
            >
              <span className="text-2xl">{i.emoji}</span>
              <span className="text-xs">{i.label}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Age group */}
      <section>
        <p className="section-label">Who's going?</p>
        <div className="grid grid-cols-3 gap-2">
          {AGE_GROUPS.map((a) => (
            <button
              key={a.value}
              type="button"
              onClick={() => setAgeGroup(a.value)}
              className={`chip flex-col gap-1 py-4 ${ageGroup === a.value ? 'chip-on' : 'chip-off'}`}
            >
              <span className="text-2xl">{a.emoji}</span>
              <span className="text-xs">{a.label}</span>
            </button>
          ))}
        </div>
      </section>

      <button type="submit" disabled={!canSubmit} className="btn-primary mt-2">
        Generate my quest ✨
      </button>
    </form>
  )
}
