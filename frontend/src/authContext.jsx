import { createContext, useContext } from 'react'
import { ClerkProvider, useAuth, useUser } from '@clerk/clerk-react'

/**
 * Auth wiring for Clerk (email/password).
 *
 * Clerk hooks must live inside <ClerkProvider>. To keep the rest of the app
 * from calling Clerk hooks directly (which would crash when Clerk isn't
 * configured), we bridge Clerk state into a plain React context. Everything
 * else reads useSession()/useClerkAuth() from that context.
 */

// Clerk publishable keys are public by design (they ship in the client bundle).
// A deployment must provide its own key; using a bundled test tenant would make
// frontend and backend authentication point at different Clerk instances.
const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
export const clerkConfigured = Boolean(PUBLISHABLE_KEY)

const AuthContext = createContext({
  account: null,
  getToken: async () => null,
  signOut: async () => {},
})

/** Reads Clerk state and republishes it as a provider-neutral context. */
function ClerkBridge({ children }) {
  const { isSignedIn, user } = useUser()
  const { getToken, signOut } = useAuth()
  const account = isSignedIn && user
    ? {
        email: user.primaryEmailAddress?.emailAddress || '',
        name: user.fullName || user.firstName || null,
      }
    : null
  return (
    <AuthContext.Provider value={{ account, getToken, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

/** Wraps the app in Clerk when configured; otherwise a null-auth context. */
export function AuthProvider({ children }) {
  if (!clerkConfigured) return children
  return (
    <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
      <ClerkBridge>{children}</ClerkBridge>
    </ClerkProvider>
  )
}

/** The signed-in account ({ email, name }) or null. Safe everywhere. */
export function useSession() {
  return useContext(AuthContext).account
}

/** { getToken, signOut } — for authenticated backend calls and sign-out. */
export function useClerkAuth() {
  const { getToken, signOut } = useContext(AuthContext)
  return { getToken, signOut }
}
