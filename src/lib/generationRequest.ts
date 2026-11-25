type Storage = {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
};

// A timeout may happen after the server has paid for and saved the briefing.
// Persist the intent BEFORE sending, so retries (including after restart) replay it.
export function createGenerationRequests<T>(
  storage: Storage,
  createId: () => string,
  send: (id: string, userId: string) => Promise<T>,
) {
  const inFlight = new Map<string, Promise<T>>();
  return (environment: string, userId: string): Promise<T> => {
    const key = `briefing-request:${environment}:${userId}`;
    const existing = inFlight.get(key);
    if (existing) return existing;
    const request = (async () => {
      let id = await storage.getItem(key);
      if (!id) {
        id = createId();
        await storage.setItem(key, id);
      }
      const result = await send(id, userId);
      // If cleanup fails, retain the same intent. Replaying a successful result
      // is safer than reporting failure or charging for another generation.
      try { await storage.removeItem(key); } catch { /* Safe to replay. */ }
      return result;
    })().finally(() => { inFlight.delete(key); });
    inFlight.set(key, request);
    return request;
  };
}
