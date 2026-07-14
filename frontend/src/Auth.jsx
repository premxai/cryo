import { useState } from 'react'
import { useSignIn, useSignUp } from '@clerk/clerk-react'
import { clerkConfigured } from './authContext'

/**
 * Auth — email/password sign-in and sign-up via Clerk, in the archive
 * auth-shell. mode: 'login' (email + password) or 'signup' (name + email +
 * password). On success, activates the session and opens the console.
 *
 * Split so Clerk hooks (useSignUp/useSignIn) only run when Clerk is configured
 * — the wrapper renders a plain "not configured" shell otherwise.
 */
export default function Auth({ mode }) {
  if (!clerkConfigured) return <AuthShell mode={mode} notConfigured />
  return <ClerkAuthForm mode={mode} />
}

function clerkErrorDetail(err) {
  return err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message || err?.message
}

function ClerkAuthForm({ mode }) {
  const isSignup = mode === 'signup'
  const { isLoaded: signUpLoaded, signUp, setActive: setActiveUp } = useSignUp()
  const { isLoaded: signInLoaded, signIn, setActive: setActiveIn } = useSignIn()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [requiresVerification, setRequiresVerification] = useState(false)
  const [status, setStatus] = useState('')
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (isSignup ? !signUpLoaded : !signInLoaded) return
    setBusy(true)
    setReady(false)
    setStatus(isSignup ? 'Creating your account…' : 'Signing in…')
    try {
      if (isSignup) {
        const res = await signUp.create({
          emailAddress: email,
          password,
        })
        if (res.status === 'complete') {
          await setActiveUp({ session: res.createdSessionId })
          finish()
        } else {
          await signUp.prepareEmailAddressVerification({ strategy: 'email_code' })
          setRequiresVerification(true)
          setStatus('We sent a verification code to your email address.')
        }
      } else {
        const res = await signIn.create({ identifier: email, password })
        if (res.status === 'complete') {
          await setActiveIn({ session: res.createdSessionId })
          finish()
        } else {
          setStatus('Additional verification is required to sign in.')
        }
      }
    } catch (err) {
      const detail = clerkErrorDetail(err)
      if (detail) {
        setStatus(detail)
        return
      }
      setStatus(err?.errors?.[0]?.message || err?.message || 'Something went wrong — try again.')
    } finally {
      setBusy(false)
    }
  }

  async function verifyEmail(e) {
    e.preventDefault()
    if (!signUpLoaded || !verificationCode.trim()) return
    setBusy(true)
    setStatus('Verifying your email…')
    try {
      const res = await signUp.attemptEmailAddressVerification({ code: verificationCode.trim() })
      if (res.status !== 'complete') {
        setStatus('That code could not complete signup. Request a new code and try again.')
        return
      }
      await setActiveUp({ session: res.createdSessionId })
      finish()
    } catch (err) {
      const detail = clerkErrorDetail(err)
      if (detail) {
        setStatus(detail)
        return
      }
      setStatus(err?.errors?.[0]?.message || err?.message || 'That code is not valid. Try again.')
    } finally {
      setBusy(false)
    }
  }

  function finish() {
    setReady(true)
    setStatus('Signed in. Opening the console…')
    setTimeout(() => { window.location.hash = '#/app' }, 500)
  }

  return (
    <AuthShell
      mode={mode}
      email={email} setEmail={setEmail}
      password={password} setPassword={setPassword}
      verificationCode={verificationCode} setVerificationCode={setVerificationCode}
      requiresVerification={requiresVerification} onVerify={verifyEmail}
      status={status} ready={ready} busy={busy} onSubmit={submit}
    />
  )
}

/** Presentational auth-shell — used for both live and not-configured states. */
function AuthShell({
  mode, notConfigured,
  email, setEmail, password, setPassword,
  verificationCode, setVerificationCode, requiresVerification, onVerify,
  status, ready, busy, onSubmit,
}) {
  const isSignup = mode === 'signup'
  const handle = requiresVerification
    ? onVerify
    : notConfigured
    ? (e) => e.preventDefault()
    : onSubmit
  const statusText = notConfigured
    ? 'Authentication is not configured yet on this deployment.'
    : (status || (isSignup
        ? 'Email and a password of 8+ characters.'
        : 'Enter your email and password.'))

  return (
    <div className="auth-shell">
      <section className="auth-intro" aria-labelledby="auth-title">
        <p className="eyebrow"><span></span> CRYO ACCOUNT / ARCHIVE ACCESS</p>
        <h1 id="auth-title">
          {isSignup ? <>Preserve your<br /><em>access.</em></> : <>Return to the<br /><em>record.</em></>}
        </h1>
        <p>
          {isSignup
            ? 'Create an account to manage API keys and run unlimited searches over the frozen corpus.'
            : 'Manage keys, run the search console, and build on a web corpus with a visible capture trail.'}
        </p>
        <dl className="auth-ledger">
          <div><dt>01 / PRIVATE</dt><dd>Your work stays in your workspace.</dd></div>
          <div><dt>02 / TRACEABLE</dt><dd>Each result retains its source ledger.</dd></div>
        </dl>
      </section>

      <section className="auth-panel" aria-labelledby="auth-form-title">
        <div className="auth-form-wrap">
          <p className="eyebrow"><span></span> {isSignup ? 'CREATE ACCOUNT' : 'ACCOUNT ACCESS'}</p>
          <h2 id="auth-form-title">
            {isSignup ? <>Sign<br /><em>up.</em></> : <>Log<br /><em>in.</em></>}
          </h2>
          <form className="auth-form" onSubmit={handle}>
            {requiresVerification ? (
              <>
                <label htmlFor="auth-verification-code">EMAIL VERIFICATION CODE</label>
                <input
                  id="auth-verification-code" type="text" required inputMode="numeric"
                  autoComplete="one-time-code" disabled={busy} placeholder="123456"
                  value={verificationCode || ''}
                  onChange={(e) => setVerificationCode?.(e.target.value)}
                />
              </>
            ) : null}
            {!requiresVerification && (
              <>
                <label htmlFor="auth-email">EMAIL ADDRESS</label>
                <input
                  id="auth-email" type="email" required autoComplete="email" disabled={notConfigured}
                  placeholder="you@company.com" value={email || ''} onChange={(e) => setEmail?.(e.target.value)}
                />
                <label htmlFor="auth-password">PASSWORD</label>
                <input
                  id="auth-password" type="password" required minLength={8} disabled={notConfigured}
                  autoComplete={isSignup ? 'new-password' : 'current-password'}
                  placeholder="At least 8 characters" value={password || ''}
                  onChange={(e) => setPassword?.(e.target.value)}
                />
              </>
            )}
            {isSignup && !requiresVerification && !notConfigured && (
              <div id="clerk-captcha" data-cl-theme="light" data-cl-size="flexible" />
            )}
            <button className="ink-button" type="submit" disabled={busy || notConfigured}>
              {requiresVerification ? 'Verify email' : isSignup ? 'Create account' : 'Log in'} <span aria-hidden="true">→</span>
            </button>
            <p className={`auth-status${ready ? ' is-ready' : ''}`} aria-live="polite">{statusText}</p>
          </form>
          <p className="auth-switch">
            {isSignup
              ? <>Already have an account? <a href="#/login">Log in.</a></>
              : <>New to CRYO? <a href="#/signup">Create your workspace.</a></>}
          </p>
        </div>
      </section>
    </div>
  )
}
