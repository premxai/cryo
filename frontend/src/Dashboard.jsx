import { useCallback, useEffect, useState } from 'react'
import { useSession, useClerkAuth } from './useSession'

const API_URL = import.meta.env.VITE_API_URL || ''

/**
 * Dashboard — API key management for a Clerk-authenticated account.
 * Signup/login happens on the Auth pages; here we just manage keys.
 */
export default function Dashboard() {
  const account = useSession()
  const { getToken, signOut } = useClerkAuth()
  const [status, setStatus] = useState('')
  const [keys, setKeys] = useState([])
  const [newKey, setNewKey] = useState(null)
  const [keyName, setKeyName] = useState('')

  // Authenticated fetch — attach the current Clerk JWT.
  const authFetch = useCallback(async (path, opts = {}) => {
    const token = await getToken()
    return fetch(`${API_URL}${path}`, {
      ...opts,
      headers: { ...(opts.headers || {}), Authorization: `Bearer ${token}` },
    })
  }, [getToken])

  const loadKeys = useCallback(() => {
    if (!account) return
    authFetch('/v1/auth/keys')
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setKeys(Array.isArray(data) ? data : []))
      .catch(() => setStatus('Could not load keys.'))
  }, [account, authFetch])

  useEffect(() => { loadKeys() }, [loadKeys])

  // Not signed in → send to login.
  useEffect(() => {
    if (account === null) {
      const t = setTimeout(() => { if (!account) window.location.hash = '#/login' }, 100)
      return () => clearTimeout(t)
    }
  }, [account])

  async function createKey(e) {
    e.preventDefault()
    const r = await authFetch('/v1/auth/keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
    await authFetch(`/v1/auth/keys/${id}`, { method: 'DELETE' })
    loadKeys()
  }

  function doSignOut() {
    signOut()
    setKeys([])
    setNewKey(null)
    window.location.hash = '#/'
  }

  if (!account) {
    return (
      <section className="dashboard-top">
        <p className="eyebrow"><span></span> ACCOUNT</p>
        <h1>Sign in to<br /><em>continue.</em></h1>
        <p>
          <a className="ink-button" href="#/login" style={{ display: 'inline-block', marginTop: '1rem' }}>
            Log in <span aria-hidden="true">→</span>
          </a>
        </p>
      </section>
    )
  }

  const activeKeys = keys.filter((k) => !k.revoked_at)

  return (
    <>
      <section className="dashboard-top">
        <p className="eyebrow"><span></span> ACCOUNT / {account.name ? `${account.name} · ` : ''}{account.email}</p>
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
            <button type="button" className="ink-button" onClick={doSignOut}>Sign out</button>
          </div>

          <form className="filter-group" style={{ margin: '1.5rem 0' }} onSubmit={createKey}>
            <input
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
