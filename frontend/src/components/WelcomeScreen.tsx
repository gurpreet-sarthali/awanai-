/**
 * WelcomeScreen - AwanAI onboarding entry point.
 *
 * Collects visitor name and email (unverified), registers them via the backend,
 * saves a local visitor session, then redirects to the dashboard.
 *
 * IMPORTANT: The email is NOT verified. Do not use it as proof of identity.
 */
import { useState } from 'react';
import { setAccessToken } from '../services/api';
import { registerVisitor } from '../services/visitorApi';
import { useVisitor, type VisitorSession } from '../context/VisitorContext';

function validateEmail(value: string): boolean {
  // RFC 5322-ish basic check
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function validateName(value: string): boolean {
  return value.trim().length >= 2;
}

export function WelcomeScreen() {
  const { saveVisitor } = useVisitor();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{ name?: string; email?: string }>({});
  const [busy, setBusy] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const validate = (): boolean => {
    const errs: { name?: string; email?: string } = {};
    const trimName = name.trim();
    const trimEmail = email.trim();

    if (!trimName) {
      errs.name = 'Please enter your full name.';
    } else if (!validateName(trimName)) {
      errs.name = 'Name must be at least 2 characters.';
    }

    if (!trimEmail) {
      errs.email = 'Please enter your email address.';
    } else if (!validateEmail(trimEmail)) {
      errs.email = 'Please enter a valid email address.';
    }

    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;

    setError('');
    if (!validate()) return;

    setBusy(true);
    try {
      const result = await registerVisitor({ name: name.trim(), email: email.trim().toLowerCase() });

      const session: VisitorSession = {
        name: result.name,
        email: result.email,
        visitorId: result.visitor_id,
        registeredAt: result.registered_at,
        accessToken: result.access_token,
      };
      if (result.access_token) {
        setAccessToken(result.access_token);
      }
      saveVisitor(session);

      setSuccessMsg(result.is_returning
        ? `Welcome back, ${result.name.split(' ')[0]}! Taking you to AwanAI…`
        : `Welcome, ${result.name.split(' ')[0]}! Setting up your chat workspace…`
      );

      // Short delay so user sees the message
      setTimeout(() => {
        window.history.pushState({}, '', '/');
        window.dispatchEvent(new PopStateEvent('popstate'));
      }, 700);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen welcome-screen">
      <div className="auth-card welcome-card">
        {/* Brand */}
        <div className="auth-brand">
          <span className="brand-mark">A</span>
          <span className="auth-brand-name">AwanAI</span>
        </div>

        <h1 className="auth-title">Welcome to AwanAI</h1>
        <p className="auth-subtitle">Your AI-powered data analytics assistant.</p>

        {/* Success State */}
        {successMsg && (
          <div className="auth-success" role="status">
            <span className="spinner" style={{ marginRight: '0.5rem' }} />
            {successMsg}
          </div>
        )}

        {/* Error Banner */}
        {error && !successMsg && (
          <div className="auth-error" role="alert">{error}</div>
        )}

        {!successMsg && (
          <form id="welcome-form" className="auth-form" onSubmit={handleSubmit} noValidate>
            {/* Full Name */}
            <div className="auth-field">
              <label htmlFor="welcome-name">Full Name</label>
              <input
                id="welcome-name"
                type="text"
                value={name}
                onChange={e => { setName(e.target.value); setFieldErrors(prev => ({ ...prev, name: undefined })); }}
                placeholder="e.g. Gurpreet Singh"
                autoComplete="name"
                autoFocus
                disabled={busy}
                aria-describedby={fieldErrors.name ? 'welcome-name-err' : undefined}
                aria-invalid={Boolean(fieldErrors.name)}
              />
              {fieldErrors.name && (
                <span id="welcome-name-err" className="auth-field-error" role="alert">{fieldErrors.name}</span>
              )}
            </div>

            {/* Email */}
            <div className="auth-field">
              <label htmlFor="welcome-email">Email Address</label>
              <input
                id="welcome-email"
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); setFieldErrors(prev => ({ ...prev, email: undefined })); }}
                placeholder="you@gmail.com"
                autoComplete="email"
                disabled={busy}
                aria-describedby={fieldErrors.email ? 'welcome-email-err' : undefined}
                aria-invalid={Boolean(fieldErrors.email)}
              />
              {fieldErrors.email && (
                <span id="welcome-email-err" className="auth-field-error" role="alert">{fieldErrors.email}</span>
              )}
              <small className="auth-hint" style={{ marginTop: '0.25rem', display: 'block' }}>
                We use this to identify your session. No verification email will be sent.
              </small>
            </div>

            <button
              id="welcome-submit"
              type="submit"
              className="button primary auth-submit"
              disabled={busy}
            >
              {busy ? <><span className="spinner" />Setting up…</> : 'Get Started →'}
            </button>
          </form>
        )}

        <p className="auth-footer" style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.8rem', opacity: 0.65 }}>
          By continuing you agree that AwanAI stores your name and email for session management only.
          No account password is required.
        </p>
      </div>
    </div>
  );
}
