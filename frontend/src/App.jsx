import { useEffect, useState } from 'react'
import Search from './Search.jsx'
import Docs from './Docs.jsx'
import Dashboard from './Dashboard.jsx'
import Playground from './Playground.jsx'
import Pricing from './Pricing.jsx'

/**
 * Parse the location hash into { route, params }.
 * Routes: #/ (search demo), #/docs, #/dashboard, #/verify?token=...
 */
function parseHash() {
  const hash = window.location.hash.replace(/^#\/?/, '')
  const [path, query] = hash.split('?')
  return { route: path || '', params: new URLSearchParams(query || '') }
}

/**
 * App — root layout with floating pill navbar and a tiny hash router.
 */
export default function App() {
  const [{ route, params }, setLocation] = useState(parseHash)

  useEffect(() => {
    const onHashChange = () => setLocation(parseHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const navLink = (href, label, active) => (
    <a
      href={href}
      className={`text-xs transition-colors font-light tracking-wide ${
        active ? 'text-white/80' : 'text-white/30 hover:text-white/60'
      }`}
    >
      {label}
    </a>
  )

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">

      {/* Floating pill navbar */}
      <header className="fixed top-4 left-0 right-0 z-50 flex justify-center px-4">
        <nav className="liquid-glass rounded-full px-6 py-2.5 flex items-center gap-5">
          <a href="#/" className="gradient-heading text-lg leading-none select-none">
            Cryo
          </a>
          <div className="w-px h-4 bg-white/10" />
          <span className="text-xs text-white/40 font-light tracking-wide hidden sm:inline">
            pre-2022 · human web
          </span>
          <div className="w-px h-4 bg-white/10 hidden sm:block" />
          {navLink('#/', 'Search', route === '')}
          {navLink('#/ask', 'Ask', route === 'ask')}
          {navLink('#/docs', 'Docs', route === 'docs')}
          {navLink('#/pricing', 'Pricing', route === 'pricing')}
          {navLink('#/dashboard', 'Keys', route === 'dashboard' || route === 'verify')}
          <a
            href="https://github.com/premxai/cryo"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-white/30 hover:text-white/60 transition-colors font-light tracking-wide"
          >
            GitHub
          </a>
        </nav>
      </header>

      {/* Main content */}
      <main className="flex-1 flex flex-col items-center pt-24 px-4">
        {route === 'ask' && <Playground />}
        {route === 'docs' && <Docs />}
        {route === 'pricing' && <Pricing />}
        {(route === 'dashboard' || route === 'verify') && (
          <Dashboard verifyToken={route === 'verify' ? params.get('token') : null} />
        )}
        {!['ask', 'docs', 'pricing', 'dashboard', 'verify'].includes(route) && <Search />}
      </main>

      {/* Footer */}
      <footer className="py-6 text-center">
        <span className="text-xs text-white/15 font-light tracking-widest">
          frozen at 2021 · authentic human content only
        </span>
      </footer>

    </div>
  )
}
