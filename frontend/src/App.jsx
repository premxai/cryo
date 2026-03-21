import { useState } from 'react'
import Search from './Search.jsx'

/**
 * App — root layout wrapper.
 * Keeps the page background dark and centres the search UI.
 */
export default function App() {
  return (
    <div className="min-h-screen bg-navy-950 text-cool-50 flex flex-col">
      {/* Top navigation bar */}
      <header className="border-b border-ice-400/10 px-6 py-3 flex items-center justify-between">
        <span className="font-mono text-xs text-ice-400/60 tracking-widest uppercase">
          Cryo / pre-2022 corpus
        </span>
        <span className="font-mono text-xs text-cool-100/30">
          {new Date().getFullYear()}
        </span>
      </header>

      {/* Main search area */}
      <main className="flex-1 flex flex-col items-center justify-start pt-20 px-4">
        <Search />
      </main>

      {/* Footer */}
      <footer className="border-t border-ice-400/10 px-6 py-3 text-center">
        <span className="font-mono text-xs text-cool-100/20">
          frozen at 2021 · authentic human content only
        </span>
      </footer>
    </div>
  )
}
