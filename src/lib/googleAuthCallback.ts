export function parseGoogleAuthCallback(value: string) {
  const callback = new URL(value);
  if (callback.protocol !== 'morningbrief:' || callback.hostname !== 'auth' || callback.pathname !== '/google'
      || callback.hash || callback.username || callback.password || callback.port
      || callback.searchParams.has('error') || callback.searchParams.has('error_code')) {
    throw new Error('Google အကောင့်ပြန်ကြားချက် မမှန်ကန်ပါ။');
  }
  const codes = callback.searchParams.getAll('code');
  if (codes.length !== 1 || !codes[0] || codes[0].length > 2048) {
    throw new Error('Google အကောင့်ကုဒ် မရရှိပါ။');
  }
  return codes[0];
}
