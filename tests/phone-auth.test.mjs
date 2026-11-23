import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

// Exercise the actual platform-independent service without loading native modules.
const source = await readFile(new URL('../src/lib/phoneAuth.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { normalizeMyanmarPhone, sendPhoneOtp, verifyPhoneOtp, phoneOtpError } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);

test('OTP configuration and delivery errors are actionable without exposing provider details', async () => {
  assert.match(phoneOtpError({ code: 'phone_provider_disabled' }), /Phone sign-in is disabled/);
  assert.match(phoneOtpError({ code: 'sms_send_failed' }), /SMS delivery failed/);
  assert.match(phoneOtpError({ status: 429 }), /Too many requests/);
  assert.match(phoneOtpError({ code: 'signup_disabled' }), /registration is disabled/);
  const client = { auth: { signInWithOtp: async () => ({ error: { code: 'phone_provider_disabled', message: 'private credential and phone' } }) } };
  await assert.rejects(sendPhoneOtp(client, '09123456789'), error => {
    assert.match(error.message, /SMS setup is required/);
    assert.doesNotMatch(error.message, /private credential/);
    return true;
  });
});

test('normalizes national and international Myanmar mobile numbers', () => {
  for (const input of ['09123456789', '9 123 456 789', '+959123456789', '959123456789']) {
    assert.equal(normalizeMyanmarPhone(input), '+959123456789');
  }
  for (const input of ['', 'abcdefghi', '+15551234567', '09123']) {
    assert.throws(() => normalizeMyanmarPhone(input));
  }
});

test('sends a real OTP request and propagates failure', async () => {
  const client = { auth: { signInWithOtp: async (request) => {
    assert.deepEqual(request, { phone: '+959123456789' });
    return { error: null };
  } } };
  assert.equal(await sendPhoneOtp(client, '09123456789'), '+959123456789');
  client.auth.signInWithOtp = async () => ({ error: new Error('provider details') });
  await assert.rejects(sendPhoneOtp(client, '09123456789'), /Could not send/);
});

test('never accepts an arbitrary six-digit code without a verified session', async () => {
  const client = { auth: { verifyOtp: async (request) => {
    assert.equal(request.type, 'sms');
    assert.equal(request.token, '123456');
    return { data: { session: null }, error: new Error('invalid') };
  } } };
  await assert.rejects(verifyPhoneOtp(client, '09123456789', '123456'), /invalid or expired/);
  await assert.rejects(verifyPhoneOtp(client, '09123456789', 'abcdef'), /six-digit/);
  const session = { user: { id: 'verified-user', is_anonymous: false } };
  client.auth.verifyOtp = async () => ({ data: { session }, error: null });
  assert.equal(await verifyPhoneOtp(client, '09123456789', '123456'), session);
  session.user.is_anonymous = true;
  await assert.rejects(verifyPhoneOtp(client, '09123456789', '123456'));
});
