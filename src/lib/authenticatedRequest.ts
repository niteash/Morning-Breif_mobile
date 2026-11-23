export type AuthSession = {
  access_token: string;
  expires_at?: number;
  user: { id: string; is_anonymous?: boolean };
};

export type SessionResult = { session: AuthSession | null; error?: unknown };
export type RequestAttempt<T> =
  | { status: number; value: T }
  | { status: number; error: unknown };

export type AuthDiagnostic = {
  requestId: string;
  route: string;
  method: string;
  category: string;
  status: number;
  tokenExpiry: "valid" | "expiring" | "expired" | "unknown";
};

export class SessionRequiredError extends Error {
  constructor(message = "Please sign in to continue.") {
    super(message);
    this.name = "SessionRequiredError";
  }
}

export class SessionRefreshUnavailableError extends Error {
  readonly status = 503;

  constructor() {
    super("Could not refresh your session. Check your connection and try again.");
    this.name = "SessionRefreshUnavailableError";
  }
}

const refreshInFlightByUser = new Map<string, Promise<SessionResult>>();

function isInvalidSessionError(error: unknown) {
  if (!error || typeof error !== "object") return false;
  const candidate = error as { status?: unknown; name?: unknown };
  return candidate.status === 400 || candidate.status === 401 || candidate.name === "AuthSessionMissingError";
}

export function tokenExpiryState(expiresAt: number | undefined, now = Date.now()): AuthDiagnostic["tokenExpiry"] {
  if (!Number.isFinite(expiresAt)) return "unknown";
  const remaining = Number(expiresAt) * 1000 - now;
  if (remaining <= 0) return "expired";
  if (remaining <= 60_000) return "expiring";
  return "valid";
}

function makeRequestId() {
  return `nt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function safeRoute(path: string) {
  return path.split("?", 1)[0].replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, ":id");
}

/** Adds one guarded refresh/retry to authenticated requests without changing server authorization. */
export async function authenticatedRequest<T>(args: {
  path: string;
  method: string;
  expectedUserId?: string;
  getSession: () => Promise<SessionResult>;
  refreshSession: () => Promise<SessionResult>;
  send: (session: AuthSession, requestId: string) => Promise<RequestAttempt<T>>;
  now?: () => number;
  requestId?: () => string;
  waitBeforeReadRetry?: () => Promise<void>;
  onDiagnostic?: (event: AuthDiagnostic) => void;
}): Promise<RequestAttempt<T>> {
  const now = args.now ?? Date.now;
  const id = (args.requestId ?? makeRequestId)();
  const route = safeRoute(args.path);
  const method = args.method.toUpperCase();
  async function refreshOnce(userId: string) {
    let refreshInFlight = refreshInFlightByUser.get(userId);
    if (!refreshInFlight) {
      refreshInFlight = Promise.resolve().then(args.refreshSession).finally(() => {
        if (refreshInFlightByUser.get(userId) === refreshInFlight) refreshInFlightByUser.delete(userId);
      });
      refreshInFlightByUser.set(userId, refreshInFlight);
    }
    let result: SessionResult;
    try {
      result = await refreshInFlight;
    } catch {
      throw new SessionRefreshUnavailableError();
    }
    if (result.error) {
      if (isInvalidSessionError(result.error)) throw new SessionRequiredError();
      throw new SessionRefreshUnavailableError();
    }
    if (!result.session || !result.session.access_token || result.session.user.is_anonymous) {
      throw new SessionRequiredError();
    }
    if (args.expectedUserId && result.session.user.id !== args.expectedUserId) {
      throw new SessionRequiredError("Your account changed. Please try again.");
    }
    return result.session;
  }

  async function currentSession() {
    let result: SessionResult;
    try {
      result = await args.getSession();
    } catch {
      throw new SessionRefreshUnavailableError();
    }
    if (!result.session) {
      if (result.error && !isInvalidSessionError(result.error)) throw new SessionRefreshUnavailableError();
      throw new SessionRequiredError();
    }
    const session = result.session;
    if (!session.access_token || session.user.is_anonymous) throw new SessionRequiredError();
    if (args.expectedUserId && session.user.id !== args.expectedUserId) {
      throw new SessionRequiredError("Your account changed. Please try again.");
    }
    const expiry = tokenExpiryState(session.expires_at, now());
    if (expiry === "expired" || expiry === "expiring") {
      const refreshed = await refreshOnce(session.user.id);
      if (refreshed.user.id !== session.user.id) throw new SessionRequiredError("Your account changed. Please try again.");
      return refreshed;
    }
    return session;
  }

  const session = await currentSession();
  let first = await args.send(session, id);
  if (first.status === 503 && method === "GET") {
    await (args.waitBeforeReadRetry?.() ?? new Promise(resolve => setTimeout(resolve, 300)));
    first = await args.send(session, id);
    args.onDiagnostic?.({
      requestId: id,
      route,
      method,
      category: first.status === 503 ? "read_retry_unavailable" : "read_retry_recovered",
      status: first.status,
      tokenExpiry: tokenExpiryState(session.expires_at, now()),
    });
  }
  if (first.status !== 401) return first;

  const expiry = tokenExpiryState(session.expires_at, now());
  args.onDiagnostic?.({ requestId: id, route, method, category: "api_unauthorized", status: 401, tokenExpiry: expiry });

  let latest: SessionResult;
  try {
    latest = await args.getSession();
  } catch {
    throw new SessionRefreshUnavailableError();
  }
  if (latest.error && !latest.session && !isInvalidSessionError(latest.error)) {
    throw new SessionRefreshUnavailableError();
  }
  if (!latest.session || latest.session.user.is_anonymous || latest.session.user.id !== session.user.id) {
    args.onDiagnostic?.({ requestId: id, route, method, category: "refresh_unavailable", status: 401, tokenExpiry: expiry });
    return first;
  }

  let retrySession = latest.session;
  if (retrySession.access_token === session.access_token) {
    try {
      retrySession = await refreshOnce(session.user.id);
    } catch (error) {
      if (error instanceof SessionRefreshUnavailableError) {
        args.onDiagnostic?.({ requestId: id, route, method, category: "refresh_service_error", status: 503, tokenExpiry: expiry });
        throw error;
      }
      args.onDiagnostic?.({ requestId: id, route, method, category: "refresh_rejected", status: 401, tokenExpiry: expiry });
      return first;
    }
  }

  if (retrySession.user.id !== session.user.id || retrySession.access_token === session.access_token) return first;
  const retried = await args.send(retrySession, id);
  args.onDiagnostic?.({
    requestId: id,
    route,
    method,
    category: retried.status === 401 ? "retry_rejected" : "retry_recovered",
    status: retried.status,
    tokenExpiry: expiry,
  });
  return retried;
}
