import { useState } from 'react'
import SetupScreen from './components/SetupScreen.jsx'
import LoadingScreen from './components/LoadingScreen.jsx'
import QuestScreen from './components/QuestScreen.jsx'
import FinishScreen from './components/FinishScreen.jsx'
import JournalScreen from './components/JournalScreen.jsx'
import { generateQuest } from './api.js'

/**
 * App — simple state-machine router, no routing library needed.
 *
 * States: 'setup' | 'loading' | 'error' | 'quest' | 'finish' | 'journal'
 */
export default function App() {
  const [screen, setScreen] = useState('setup')
  const [questResponse, setQuestResponse] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [setupParams, setSetupParams] = useState(null)

  // ── Setup → Loading → Quest ────────────────────────────────────────────────
  async function handleSetupSubmit(params) {
    setSetupParams(params)
    setScreen('loading')
    setErrorMsg('')
    try {
      const data = await generateQuest(params)
      setQuestResponse(data)
      setScreen('quest')
    } catch (err) {
      setErrorMsg(err.message || 'Something went wrong. Is the backend running?')
      setScreen('error')
    }
  }

  // ── Quest → Finish ─────────────────────────────────────────────────────────
  function handleQuestComplete() {
    setScreen('finish')
  }

  // ── Finish → Setup (new quest) ─────────────────────────────────────────────
  function handleNewQuest() {
    setQuestResponse(null)
    setSetupParams(null)
    setScreen('setup')
  }

  // ── Nav to Journal ─────────────────────────────────────────────────────────
  function handleOpenJournal() {
    setScreen('journal')
  }

  function handleCloseJournal() {
    setScreen(questResponse ? 'finish' : 'setup')
  }

  // ── Error retry ────────────────────────────────────────────────────────────
  async function handleRetry() {
    if (setupParams) {
      await handleSetupSubmit(setupParams)
    } else {
      setScreen('setup')
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-forest-950 flex flex-col">
      {/* Top nav bar — always visible except during quest */}
      {screen !== 'quest' && (
        <header className="flex items-center justify-between px-5 pt-5 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🌿</span>
            <span className="font-bold text-forest-400 text-lg tracking-tight">WildQuest</span>
          </div>
          {screen !== 'journal' && (
            <button
              onClick={handleOpenJournal}
              className="text-stone-400 hover:text-forest-400 transition-colors text-sm font-semibold flex items-center gap-1"
              aria-label="Open journal"
            >
              <span>📓</span> Journal
            </button>
          )}
          {screen === 'journal' && (
            <button
              onClick={handleCloseJournal}
              className="text-stone-400 hover:text-forest-400 transition-colors text-sm font-semibold"
            >
              ← Back
            </button>
          )}
        </header>
      )}

      {/* Screen switcher */}
      <main className="flex-1 flex flex-col">
        {screen === 'setup' && (
          <SetupScreen onSubmit={handleSetupSubmit} />
        )}

        {screen === 'loading' && (
          <LoadingScreen />
        )}

        {screen === 'error' && (
          <ErrorScreen message={errorMsg} onRetry={handleRetry} onBack={() => setScreen('setup')} />
        )}

        {screen === 'quest' && questResponse && (
          <QuestScreen
            questResponse={questResponse}
            onComplete={handleQuestComplete}
          />
        )}

        {screen === 'finish' && questResponse && (
          <FinishScreen
            questResponse={questResponse}
            onNewQuest={handleNewQuest}
            onOpenJournal={handleOpenJournal}
          />
        )}

        {screen === 'journal' && (
          <JournalScreen />
        )}
      </main>
    </div>
  )
}

// ── Inline error screen (too small for its own file) ──────────────────────────
function ErrorScreen({ message, onRetry, onBack }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 gap-6 animate-fade-up">
      <div className="text-6xl">🌧️</div>
      <div className="text-center">
        <h2 className="text-2xl font-bold text-stone-100 mb-2">Couldn't reach the trail</h2>
        <p className="text-stone-400 text-sm leading-relaxed max-w-xs">
          {message}
        </p>
        <p className="text-stone-500 text-xs mt-3">
          Make sure the backend is running: <code className="text-forest-400">uvicorn main:app --reload</code>
        </p>
      </div>
      <div className="w-full max-w-xs flex flex-col gap-3">
        <button onClick={onRetry} className="btn-primary">Try again</button>
        <button onClick={onBack} className="btn-secondary">Change settings</button>
      </div>
    </div>
  )
}
