import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const configure = require('../app.config.js');
const base = { android: { package: 'com.example.app', googleServicesFile: './google-services.json' } };
const names = [
  'EAS_BUILD_PROFILE', 'EAS_BUILD_PLATFORM', 'EXPO_PUBLIC_API_URL',
  'EXPO_PUBLIC_SUPABASE_URL', 'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
  'EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY', 'EXPO_PUBLIC_REVENUECAT_ENTITLEMENT_ID',
  'GOOGLE_SERVICES_JSON', 'EXPO_PUBLIC_ADS_ENABLED', 'ADMOB_ANDROID_APP_ID',
  'ADMOB_IOS_APP_ID', 'EXPO_PUBLIC_ADMOB_BANNER_UNIT_ID',
];

function withEnvironment(values, run) {
  const previous = Object.fromEntries(names.map(name => [name, process.env[name]]));
  for (const name of names) delete process.env[name];
  Object.assign(process.env, values);
  try { return run(); }
  finally {
    for (const name of names) {
      if (previous[name] === undefined) delete process.env[name];
      else process.env[name] = previous[name];
    }
  }
}

test('production Android config rejects incomplete or temporary infrastructure', () => {
  const common = { EAS_BUILD_PROFILE: 'production', EAS_BUILD_PLATFORM: 'android' };
  assert.throws(() => withEnvironment(common, () => configure({ config: base })), /EXPO_PUBLIC_API_URL/);
  assert.throws(() => withEnvironment({ ...common, EXPO_PUBLIC_API_URL: 'https://demo.trycloudflare.com' }, () => configure({ config: base })), /stable HTTPS/);
});

test('production Android config accepts only the complete external contract', () => {
  const result = withEnvironment({
    EAS_BUILD_PROFILE: 'production', EAS_BUILD_PLATFORM: 'android',
    EXPO_PUBLIC_API_URL: 'https://api.naythit.example',
    EXPO_PUBLIC_SUPABASE_URL: 'https://project.supabase.co',
    EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'public-key',
    EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY: 'goog_public-key',
    EXPO_PUBLIC_REVENUECAT_ENTITLEMENT_ID: 'premium',
    GOOGLE_SERVICES_JSON: '/run/secrets/google-services.json',
  }, () => configure({ config: base }));
  assert.equal(result.android.googleServicesFile, '/run/secrets/google-services.json');
  assert.ok(result.plugins.some(plugin => Array.isArray(plugin) && plugin[0] === 'react-native-google-mobile-ads'));
});

test('enabled production ads require real AdMob identifiers', () => {
  const common = {
    EAS_BUILD_PROFILE: 'production', EAS_BUILD_PLATFORM: 'android',
    EXPO_PUBLIC_API_URL: 'https://api.naythit.example',
    EXPO_PUBLIC_SUPABASE_URL: 'https://project.supabase.co',
    EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'public-key',
    EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY: 'goog_public-key',
    EXPO_PUBLIC_REVENUECAT_ENTITLEMENT_ID: 'premium',
    GOOGLE_SERVICES_JSON: '/run/secrets/google-services.json',
    EXPO_PUBLIC_ADS_ENABLED: 'true',
  };
  assert.throws(() => withEnvironment(common, () => configure({ config: base })), /ADMOB_ANDROID_APP_ID/);
  const result = withEnvironment({
    ...common,
    ADMOB_ANDROID_APP_ID: 'ca-app-pub-real~app',
    EXPO_PUBLIC_ADMOB_BANNER_UNIT_ID: 'ca-app-pub-real/banner',
  }, () => configure({ config: base }));
  assert.equal(result.plugins.at(-1)[1].androidAppId, 'ca-app-pub-real~app');
});
