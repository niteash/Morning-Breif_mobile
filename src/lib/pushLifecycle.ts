// Serialize native registration and logout so a late registration cannot restore
// a token after cleanup. Failed cleanup leaves authentication available to retry.
export function createPushLifecycle<T>(
  register: () => Promise<T>,
  unregister: () => Promise<void>,
  signOut: () => Promise<void>,
) {
  let tail: Promise<unknown> = Promise.resolve();
  let logout: Promise<void> | undefined;
  return {
    register(): Promise<T | null> {
      if (logout) return Promise.resolve(null);
      const result = tail.then(() => logout ? null : register());
      tail = result.catch(() => undefined);
      return result;
    },
    signOut(): Promise<void> {
      if (logout) return logout;
      logout = tail.then(async () => {
        await unregister();
        await signOut();
      }).finally(() => { logout = undefined; });
      tail = logout.catch(() => undefined);
      return logout;
    },
  };
}
