import { useCallback, useEffect, useState } from 'react'
import { useSession, setSession as saveSession, clearSession } from './useSession'

const API_URL = import.meta.env.VITE_API_URL || ''

/**
 * Dashboard — magic-link sign-in plus API key management.
 * Also handles the #/verify?token=... landing from the emailed link.
 */
export default function Dashboard({ verifyToken }) {
  const session = useSession()
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('')
  const [statusReady, setStatusReady] = useState(false)
  const [keys, setKeys] = useState([])
  const [newKey, setNewKey] = useState(null)
  const [keyName, setKeyName] = useState('')

  const authHeaders = useCallback(
    () => ({ Authorization: `Bearer ${session?.session_token}` }),
    [session],
  )

  // Exchange a magic-link token for a session on #/verify
  useEffect(() => {
    if (!verifyToken) return
    fetch(`${API_URL}/v1/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: verifyToken }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then((data) => {
        saveSession(data)
        window.location.hash = '#/dashboard'
      })
      .catch(() => setStatus('Sign-in link is invalid or expired — request a new one.'))
  }, [verifyToken])

  const loadKeys = useCallback(() => {
    if (!session) return
    fetch(`${API_URL}/v1/auth/keys`, { headers: authHeaders() })
      .then((r) => {
        if (r.status === 401) {
          clearSession()
          return []
        }
        return r.json()
      })
      .then((data) => setKeys(Array.isArray(data) ? data : []))
      .catch(() => setStatus('Could not load keys.'))
  }, [session, authHeaders])

  useEffect(() => { loadKeys() }, [loadKeys])

  async function requestLink(e) {
    e.preventDefault()
    setStatusReady(false)
    setStatus('Sending…')
    const r = await fetch(`${API_URL}/v1/auth/magic-link`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
    setStatusReady(r.ok)
    setStatus(r.ok ? 'Check your email for a sign-in link.' : 'Something went wrong — try again.')
  }

  async function createKey(e) {
    e.preventDefault()
    const r = await fetch(`${API_URL}/v1/auth/keys`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: keyName || 'default' }),
    })
    if (r.ok) {
      const data = await r.json()
      setNewKey(data.key)
      setKeyName('')
      loadKeys()
    } else {
      const body = await r.json().catch(() => ({}))
      setStatus(body?.error?.message || 'Could not create key.')
    }
  }

  async function revokeKey(id) {
    await fetch(`${API_URL}/v1/auth/keys/${id}`, { method: 'DELETE', headers: authHeaders() })
    loadKeys()
  }

  function signOut() {
    clearSession()
    setKeys([])
    setNewKey(null)
  }

  // ── Signed out: magic-link auth shell ─────────────────────────────────────
  if (!session) {
    return (
      <div className="auth-shell">
        <section className="auth-intro" aria-labelledby="login-title">
          <p className="eyebrow"><span></span> CRYO ACCOUNT / ARCHIVE ACCESS</p>
          <h1 id="login-title">Return to the<br /><em>record.</em></h1>
          <p>Manage keys and build on a web corpus with a visible capture trail. No password — we send a magic link.</p>
          <dl className="auth-ledger">
            <div><dt>01 / PRIVATE</dt><dd>Your work stays in your workspace.</dd></div>
            <div><dt>02 / TRACEABLE</dt><dd>Each result retains its source ledger.</dd></div>
          </dl>
        </section>
        <section className="auth-panel" aria-labelledby="auth-form-title">
          <div className="auth-form-wrap">
            <p className="eyebrow"><span></span> ACCOUNT ACCESS</p>
            <h2 id="auth-form-title">Sign<br /><em>in.</em></h2>
            <form className="auth-form" onSubmit={requestLink}>
              <label htmlFor="login-email">EMAIL ADDRESS</label>
              <input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <button className="ink-button" type="submit">Send magic link <span aria-hidden="true">→</span></button>
              <p className={`auth-status${statusReady ? ' is-ready' : ''}`} aria-live="polite">
                {status || 'A one-time sign-in link will be emailed to you.'}
              </p>
            </form>
            <p className="auth-switch">
              New to CRYO? The same link creates your workspace.
            </p>
          </div>
        </section>
      </div>
    )
  }

  // ── Signed in: dashboard ──────────────────────────────────────────────────
  const activeKeys = keys.filter((k) => !k.revoked_at)

  return (
    <>
      <section className="dashboard-top">
        <p className="eyebrow"><span></span> ACCOUNT / {session.email}</p>
        <h1>Keys with<br /><em>consequences.</em></h1>
        <p>Create a named key, use it across REST, SDK, and MCP, and revoke it the moment it leaks.</p>
        <a className="ink-button" href="#/app" style={{ display: 'inline-block', marginTop: '1.5rem' }}>
          Open search console <span aria-hidden="true">→</span>
        </a>
      </section>

      <section className="usage-strip">
        <div><span>ACTIVE KEYS</span><strong>{String(activeKeys.length).padStart(2, '0')}</strong></div>
        <div><span>FREE QUOTA</span><strong>1,000 <small>/ mo</small></strong></div>
        <div><span>RATE</span><strong>60 <small>/ min</small></strong></div>
        <a href="#/pricing">View limits <span aria-hidden="true">→</span></a>
      </section>

      <section className="dashboard-grid">
        <section className="key-area">
          <div className="section-head">
            <div>
              <p className="eyebrow"><span></span> API KEYS</p>
              <h2>One key,<br />one clear owner.</h2>
            </div>
            <button type="button" className="ink-button" onClick={signOut}>Sign out</button>
          </div>

          <form className="filter-group" style={{ margin: '1.5rem 0' }} onSubmit={createKey}>
            <input
              className="year-range"
              style={{ border: '1px solid var(--line)', background: 'rgba(255,255,255,.34)', padding: '.6rem .7rem', font: '400 12px var(--mono)', width: '14rem' }}
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              placeholder="e.g. research-agent"
              maxLength={100}
            />
            <button type="submit" className="ink-button">Create key <span aria-hidden="true">+</span></button>
          </form>

          {newKey && (
            <div className="new-key-note">
              <p>Store this now — shown in full only once</p>
              <code>{newKey}</code>
            </div>
          )}

          {activeKeys.length === 0 && !keys.length ? (
            <div className="key-empty">
              <p>No keys yet.</p>
              <span>Create a named key. It will be shown in full exactly once, then masked.</span>
            </div>
          ) : (
            <div className="key-list">
              {keys.map((k) => (
                <div className="key-row" key={k.id}>
                  <b>{k.name}</b>
                  <span>
                    <code>{k.key_prefix}…</code>
                    {k.revoked_at
                      ? <span className="revoked"> · revoked</span>
                      : ` · ${k.last_used_at ? `used ${new Date(k.last_used_at).toLocaleDateString()}` : 'never used'}`}
                  </span>
                  {k.revoked_at
                    ? <span className="revoked">REVOKED</span>
                    : <button className="revoke-key" type="button" onClick={() => revokeKey(k.id)}>Revoke</button>}
                </div>
              ))}
            </div>
          )}
          {status && <p className="side-note">{status}</p>}
        </section>

        <section className="usage-area">
          <p className="eyebrow"><span></span> REQUEST LEDGER</p>
          <h2>Where the<br />units <em>went.</em></h2>
          <dl>
            {activeKeys.length === 0 && (
              <div><dt>No active keys</dt><dd>—</dd></div>
            )}
            {activeKeys.map((k) => (
              <div key={k.id}>
                <dt>{k.name}</dt>
                <dd>{k.monthly_quota.toLocaleString()} / mo</dd>
              </div>
            ))}
          </dl>
          <p className="side-note">
            Per-endpoint counts for the current period come from <b>GET /v1/usage</b> called with
            a key. This surface never fabricates usage it cannot read.
          </p>
        </section>
      </section>
    </>
  )
}
