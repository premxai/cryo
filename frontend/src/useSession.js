import { useEffect, useState } from 'react'

/**
 * Shared magic-link session state, stored in localStorage under `cryo_session`.
 * Components read it with useSession(); Dashboard writes it with set/clearSession
 * so the header and gated pages update live (via a custom event + storage event).
 */
export const SESSION_KEY = 'cryo_session'
const EVENT = 'cryo-session-change'

export function getSession() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY)) } catch { return null }
}

export function setSession(data) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(data))
  window.dispatchEvent(new Event(EVENT))
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY)
  window.dispatchEvent(new Event(EVENT))
}

export function useSession() {
  const [session, setSessionState] = useState(getSession)
  useEffect(() => {
    const handler = () => setSessionState(getSession())
    window.addEventListener(EVENT, handler)
    window.addEventListener('storage', handler)
    return () => {
      window.removeEventListener(EVENT, handler)
      window.removeEventListener('storage', handler)
    }
  }, [])
  return session
}
