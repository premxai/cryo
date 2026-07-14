import { useEffect, useState } from 'react'
import Search from './Search.jsx'
import AppSearch from './AppSearch.jsx'
import Docs from './Docs.jsx'
import Dashboard from './Dashboard.jsx'
import Auth from './Auth.jsx'
import Playground from './Playground.jsx'
import Pricing from './Pricing.jsx'
import { useSession, useClerkAuth } from './useSession.js'
import brandMark from './assets/cryo-archive-mark.png'

/**
 * Parse the location hash into { route, params }.
 * Routes: #/ (landing), #/app (console), #/ask, #/docs, #/pricing,
 *         #/dashboard, #/login, #/signup.
 */
function parseHash() {
  const hash = window.location.hash.replace(/^#\/?/, '')
  const [path, query] = hash.split('?')
  return { route: path || '', params: new URLSearchParams(query || '') }
}

// Anonymous visitors see the marketing surfaces.
const PUBLIC_NAV = [
  { href: '#/', label: 'Search', match: (r) => r === '' },
  { href: '#/ask', label: 'Ask', match: (r) => r === 'ask' },
  { href: '#/docs', label: 'Docs', match: (r) => r === 'docs' },
  { href: '#/pricing', label: 'Pricing', match: (r) => r === 'pricing' },
]

// Signed-in members get the product surfaces — no public Search/Ask.
const AUTHED_NAV = [
  { href: '#/app', label: 'Console', match: (r) => r === 'app' },
  { href: '#/dashboard', label: 'Keys', match: (r) => r === 'dashboard' },
  { href: '#/docs', label: 'Docs', match: (r) => r === 'docs' },
  { href: '#/pricing', label: 'Pricing', match: (r) => r === 'pricing' },
]

// Routes a signed-in member shouldn't land on — bounce them to the console.
const MEMBER_REDIRECT = new Set(['', 'ask', 'login', 'signup'])

/**
 * App — archive-editorial shell: three-tier header, hash router, footer.
 */
export default function App() {
  const [{ route }, setLocation] = useState(parseHash)
  const [menuOpen, setMenuOpen] = useState(false)
  const session = useSession()
  const { signOut } = useClerkAuth()

  useEffect(() => {
    const onHashChange = () => { setLocation(parseHash()); setMenuOpen(false) }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  // Signed-in members never see the public Search/Ask/auth pages.
  useEffect(() => {
    if (session && MEMBER_REDIRECT.has(route)) window.location.hash = '#/app'
  }, [session, route])

  const isHome = route === '' && !session
  const nav = session ? AUTHED_NAV : PUBLIC_NAV
  const homeHref = session ? '#/app' : '#/'

  const footers = {
    '': ['CRYO / FROZEN WEB INFRASTRUCTURE', 'STATUS: LIVE CORPUS', '© 2026'],
    app: ['CRYO / SEARCH CONSOLE', 'AUTHENTICATED', '© 2026'],
    ask: ['CRYO / GROUNDED Q&A', 'NO SILENT SYNTHESIS', '© 2026'],
    docs: ['CRYO / API REFERENCE', 'V1 / DOCUMENTATION', '© 2026'],
    pricing: ['CRYO / QUOTA POLICY', 'PAID BILLING: NOT LIVE', '© 2026'],
    dashboard: ['CRYO / ACCOUNT SURFACE', 'PASSWORD AUTH', '© 2026'],
    login: ['CRYO / ACCOUNT ACCESS', 'PASSWORD AUTH', '© 2026'],
    signup: ['CRYO / ACCOUNT ACCESS', 'PASSWORD AUTH', '© 2026'],
  }
  const foot = footers[route] || footers['']

  return (
    <div className={isHome ? 'home' : 'interior'}>
      <a className="skip-link" href="#main">Skip to content</a>

      <header className="site-header">
        <a className="brand" href={homeHref} aria-label="CRYO home">
          <img src={brandMark} alt="" />
          <span>CRYO</span>
        </a>
        <button
          className="menu-button"
          type="button"
          aria-expanded={menuOpen}
          aria-controls="site-nav"
          onClick={() => setMenuOpen((v) => !v)}
        >
          Menu <span aria-hidden="true">+</span>
        </button>
        <nav className={`site-nav${menuOpen ? ' is-open' : ''}`} id="site-nav" aria-label="Primary navigation">
          {nav.map((n) => (
            <a key={n.href} href={n.href} aria-current={n.match(route) ? 'page' : undefined}>
              {n.label}
            </a>
          ))}
        </nav>
        <div className="header-actions" aria-label="Account actions">
          {session ? (
            <>
              <span className="account-link" style={{ color: 'var(--muted)', cursor: 'default' }}>
                {session.email}
              </span>
              <button
                className="key-link"
                type="button"
                onClick={async () => { await signOut(); window.location.hash = '#/' }}
                style={{ font: '500 11px var(--mono)', textTransform: 'uppercase' }}
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <a className="account-link" href="#/login" aria-current={route === 'login' ? 'page' : undefined}>Log in</a>
              <a className="signup-link" href="#/signup" aria-current={route === 'signup' ? 'page' : undefined}>Sign up</a>
              <a
                className="key-link"
                href="#/signup"
                aria-current={route === 'dashboard' ? 'page' : undefined}
              >
                Get API key <span aria-hidden="true">↗</span>
              </a>
            </>
          )}
        </div>
      </header>

      <main id="main">
        {route === 'app' && <AppSearch />}
        {route === 'ask' && <Playground />}
        {route === 'docs' && <Docs />}
        {route === 'pricing' && <Pricing />}
        {route === 'login' && <Auth mode="login" />}
        {route === 'signup' && <Auth mode="signup" />}
        {route === 'dashboard' && <Dashboard />}
        {!['app', 'ask', 'docs', 'pricing', 'dashboard', 'login', 'signup'].includes(route) && <Search />}
      </main>

      <footer className="site-footer">
        <span>{foot[0]}</span>
        <span>{foot[1]}</span>
        <span>{foot[2]}</span>
      </footer>
    </div>
  )
}
