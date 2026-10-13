/**
 * VisitorContext - lightweight, unverified visitor session for AwanAI.
 *
 * SECURITY NOTE:
 * The name and email stored here are NOT verified credentials. They are
 * self-reported by the visitor and must NOT be used for access control or
 * to prove identity. They are persisted only for UX convenience (displaying
 * the visitor's name, avoiding re-entry on page refresh).
 *
 * Features protected by real JWT authentication (backend /api/v1/auth/*)
 * remain separate from this visitor session.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { clearAccessToken, getAccessToken, setAccessToken } from '../services/api';
import { registerVisitor } from '../services/visitorApi';

export interface VisitorSession {
  /** Self-reported display name - NOT verified */
  name: string;
  /** Self-reported email address - NOT verified */
  email: string;
  /** Supabase-generated visitor ID (UUID) - used for dataset isolation */
  visitorId: string;
  /** ISO timestamp of when this session was created */
  registeredAt: string;
  /** Temporary visitor session JWT issued by backend */
  accessToken?: string;
}

type VisitorContextValue = {
  visitor: VisitorSession | null;
  isLoading: boolean;
  /** Save a new visitor session (called after backend registration). */
  saveVisitor: (session: VisitorSession) => void;
  /** Clear the session (e.g., "Start over" button). */
  clearVisitor: () => void;
};

const SESSION_KEY = 'awanai.visitorSession';
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

const VisitorContext = createContext<VisitorContextValue | null>(null);

function readSession(): VisitorSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { session: VisitorSession; expiresAt: number };
    if (Date.now() > parsed.expiresAt) {
      localStorage.removeItem(SESSION_KEY);
      return null;
    }
    const s = parsed.session;
    if (!s?.visitorId || !s?.name || !s?.email) return null;
    return s;
  } catch {
    return null;
  }
}

function writeSession(session: VisitorSession): void {
  try {
    localStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ session, expiresAt: Date.now() + SESSION_TTL_MS }),
    );
  } catch {
    /* Storage unavailable - proceed without persistence */
  }
}

export function VisitorProvider({ children }: { children: React.ReactNode }) {
  const [visitor, setVisitor] = useState<VisitorSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session from localStorage on mount and ensure active JWT token
  useEffect(() => {
    const restored = readSession();
    setVisitor(restored);
    if (restored) {
      if (restored.accessToken) {
        setAccessToken(restored.accessToken);
      }
      // If token is missing from localStorage or needs refresh, fetch one quietly
      const currentToken = getAccessToken();
      if (!currentToken || !restored.accessToken) {
        registerVisitor({ name: restored.name, email: restored.email })
          .then(res => {
            if (res.access_token) {
              setAccessToken(res.access_token);
              const updated = { ...restored, accessToken: res.access_token };
              writeSession(updated);
              setVisitor(updated);
            }
          })
          .catch(() => {
            /* Backend unreachable, maintain offline visitor session */
          });
      }
    }
    setIsLoading(false);
  }, []);

  const saveVisitor = useCallback((session: VisitorSession) => {
    writeSession(session);
    if (session.accessToken) {
      setAccessToken(session.accessToken);
    }
    setVisitor(session);
  }, []);

  const clearVisitor = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    clearAccessToken();
    setVisitor(null);
  }, []);

  const value = useMemo(
    () => ({ visitor, isLoading, saveVisitor, clearVisitor }),
    [visitor, isLoading, saveVisitor, clearVisitor],
  );

  return <VisitorContext.Provider value={value}>{children}</VisitorContext.Provider>;
}

export function useVisitor() {
  const ctx = useContext(VisitorContext);
  if (!ctx) throw new Error('useVisitor must be used within VisitorProvider');
  return ctx;
}
