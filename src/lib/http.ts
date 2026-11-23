export async function requestJson(url: string, options: RequestInit = {}, timeoutMs = 30_000) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  options.signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (!response.ok) {
      // Never display or log provider errors, proxy HTML, signed URLs or tokens.
      let message = response.status === 401 ? "Your session has expired. Please sign in again."
        : response.status === 403 ? "This action is not available for your account."
        : response.status === 409 ? "Your briefing is already being prepared. Please wait and refresh."
        : response.status === 429 ? "Too many requests. Please try again later."
        : response.status === 422 ? "Please check your entries and try again."
        : "The service is temporarily unavailable. Please try again.";
      // Accept only known error codes, never arbitrary backend/provider text.
      let code: string | undefined;
      let retryAfterSeconds: number | undefined;
      try {
        const body = await response.json();
        const detail = body?.detail;
        const messages: Record<string, string> = {
          generation_disabled: 'Audio generation is disabled on this staging backend. A separately authorized audio test is required.',
          generation_cooldown: 'The previous generation failed. Wait for the cooldown before retrying.',
          generation_in_progress: 'Your briefing is being prepared. Refresh its status instead of generating again.',
          generation_busy: 'Generation is busy. Refresh the briefing status.',
          generation_limit_reached: 'Today’s regeneration limit has been reached. Your latest ready audio is still available.',
          no_recent_news: 'No fresh stories are available in your selected categories. Change categories or try again after the feeds refresh.',
        };
        if (typeof detail?.code === 'string' && Object.hasOwn(messages, detail.code)) {
          code = detail.code;
          message = messages[detail.code];
          if (Number.isInteger(detail.retry_after_seconds) && detail.retry_after_seconds >= 0 && detail.retry_after_seconds <= 86400) {
            retryAfterSeconds = detail.retry_after_seconds;
            message += ` Retry after ${retryAfterSeconds} seconds.`;
          }
        }
      } catch { /* Keep safe status-based fallback for non-JSON errors. */ }
      throw new ApiError(message, response.status, code, retryAfterSeconds);
    }
    if (response.status === 204) return null;
    if (!response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("The service returned an unexpected response. Please try again.");
    }
    return await response.json();
  } catch (error) {
    if (controller.signal.aborted) throw new Error("The request was cancelled or timed out. Please try again.");
    if (error instanceof TypeError) throw new Error("Unable to connect. Check your internet connection.");
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}
export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly code?: string, public readonly retryAfterSeconds?: number) {
    super(message);
    this.name = "ApiError";
  }
}
