import { useCallback, useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || ''
const SESSION_KEY = 'cryo_session'

/**
 * Dashboard — magic-link sign-in plus API key management.
 * Also handles the #/verify?token=... landing from the emailed link.
 */
export default function Dashboard({ verifyToken }) {
  const [session, setSession] = useState(() => {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY)) } catch { return null }
  })
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('')
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
        localStorage.setItem(SESSION_KEY, JSON.stringify(data))
        setSession(data)
        window.location.hash = '#/dashboard'
      })
      .catch(() => setStatus('Sign-in link is invalid or expired — request a new one.'))
  }, [verifyToken])

  const loadKeys = useCallback(() => {
    if (!session) return
    fetch(`${API_URL}/v1/auth/keys`, { headers: authHeaders() })
      .then((r) => {
        if (r.status === 401) {
          localStorage.removeItem(SESSION_KEY)
          setSession(null)
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
    setStatus('Sending…')
    const r = await fetch(`${API_URL}/v1/auth/magic-link`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
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
    localStorage.removeItem(SESSION_KEY)
    setSession(null)
    setKeys([])
  }

  if (!session) {
    return (
      <div className="w-full max-w-md pb-16">
        <h1 className="gradient-heading text-3xl mb-2">API Keys</h1>
        <p className="text-sm text-white/50 mb-8 font-light">
          Sign in with your email — no password, we send a magic link.
        </p>
        <form onSubmit={requestLink} className="flex gap-2">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="flex-1 liquid-glass rounded-full px-5 py-2.5 text-sm bg-transparent text-white placeholder-white/30 focus:outline-none"
          />
          <button
            type="submit"
            className="liquid-glass rounded-full px-5 py-2.5 text-sm text-white/80 hover:text-white transition-colors"
          >
            Send link
          </button>
        </form>
        {status && <p className="text-xs text-white/40 mt-4">{status}</p>}
      </div>
    )
  }

  return (
    <div className="w-full max-w-3xl pb-16">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="gradient-heading text-3xl mb-1">API Keys</h1>
          <p className="text-xs text-white/40 font-light">{session.email}</p>
        </div>
        <button onClick={signOut} className="text-xs text-white/30 hover:text-white/60 transition-colors">
          Sign out
        </button>
      </div>

      {newKey && (
        <div className="liquid-glass rounded-xl p-4 mb-6 border border-white/10">
          <div className="text-xs text-white/50 mb-2">
            Your new key — copy it now, it will not be shown again:
          </div>
          <code className="text-sm text-emerald-300 break-all select-all">{newKey}</code>
        </div>
      )}

      <form onSubmit={createKey} className="flex gap-2 mb-8">
        <input
          value={keyName}
          onChange={(e) => setKeyName(e.target.value)}
          placeholder="Key name (optional)"
          maxLength={100}
          className="flex-1 liquid-glass rounded-full px-5 py-2.5 text-sm bg-transparent text-white placeholder-white/30 focus:outline-none"
        />
        <button
          type="submit"
          className="liquid-glass rounded-full px-5 py-2.5 text-sm text-white/80 hover:text-white transition-colors"
        >
          Create key
        </button>
      </form>

      <div className="space-y-3">
        {keys.map((k) => (
          <div key={k.id} className="liquid-glass rounded-xl p-4 flex items-center justify-between">
            <div>
              <div className="text-sm text-white/80">
                <code>{k.key_prefix}…</code>
                <span className="ml-3 text-white/40">{k.name}</span>
                {k.revoked_at && <span className="ml-3 text-red-400/70 text-xs">revoked</span>}
              </div>
              <div className="text-xs text-white/30 mt-1 font-light">
                {k.monthly_quota.toLocaleString()} req/mo · {k.rate_limit_per_minute} req/min ·{' '}
                {k.last_used_at ? `last used ${new Date(k.last_used_at).toLocaleDateString()}` : 'never used'}
              </div>
            </div>
            {!k.revoked_at && (
              <button
                onClick={() => revokeKey(k.id)}
                className="text-xs text-white/30 hover:text-red-400/80 transition-colors"
              >
                Revoke
              </button>
            )}
          </div>
        ))}
        {keys.length === 0 && (
          <p className="text-sm text-white/30 font-light">No keys yet — create one above.</p>
        )}
      </div>
      {status && <p className="text-xs text-white/40 mt-4">{status}</p>}
    </div>
  )
}
