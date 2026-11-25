function requiredProductionValue(name, value) {
  if (!value || !value.trim()) throw new Error(`Missing production build variable: ${name}`);
  return value.trim();
}

module.exports = ({ config }) => {
  const productionAndroid = process.env.EAS_BUILD_PROFILE === 'production'
    && process.env.EAS_BUILD_PLATFORM === 'android';
  const apiUrl = productionAndroid
    ? requiredProductionValue('EXPO_PUBLIC_API_URL', process.env.EXPO_PUBLIC_API_URL)
    : process.env.EXPO_PUBLIC_API_URL;
  const adsEnabled = process.env.EXPO_PUBLIC_ADS_ENABLED === 'true';
  const testAndroidAppId = 'ca-app-pub-3940256099942544~3347511713';
  const testIosAppId = 'ca-app-pub-3940256099942544~1458002511';
  let androidAdMobAppId = process.env.ADMOB_ANDROID_APP_ID || testAndroidAppId;
  let iosAdMobAppId = process.env.ADMOB_IOS_APP_ID || testIosAppId;
  if (productionAndroid) {
    const parsed = new URL(apiUrl);
    const blocked = parsed.protocol !== 'https:' || ['localhost', '127.0.0.1'].includes(parsed.hostname)
      || parsed.hostname.endsWith('.trycloudflare.com') || parsed.hostname.endsWith('.ngrok-free.app')
      || parsed.hostname === 'api.example.com';
    if (blocked) throw new Error('Production EXPO_PUBLIC_API_URL must be a stable HTTPS backend');
    requiredProductionValue('EXPO_PUBLIC_SUPABASE_URL', process.env.EXPO_PUBLIC_SUPABASE_URL);
    requiredProductionValue('EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY', process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
    requiredProductionValue('EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY', process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY);
    requiredProductionValue('EXPO_PUBLIC_REVENUECAT_ENTITLEMENT_ID', process.env.EXPO_PUBLIC_REVENUECAT_ENTITLEMENT_ID);
    requiredProductionValue('GOOGLE_SERVICES_JSON', process.env.GOOGLE_SERVICES_JSON);
    if (adsEnabled) {
      androidAdMobAppId = requiredProductionValue('ADMOB_ANDROID_APP_ID', process.env.ADMOB_ANDROID_APP_ID);
      requiredProductionValue('EXPO_PUBLIC_ADMOB_BANNER_UNIT_ID', process.env.EXPO_PUBLIC_ADMOB_BANNER_UNIT_ID);
    }
  }
  return {
    ...config,
    plugins: [
      ...(config.plugins || []),
      ['react-native-google-mobile-ads', {
        androidAppId: androidAdMobAppId,
        iosAppId: iosAdMobAppId,
        delayAppMeasurementInit: true,
        optimizeInitialization: true,
        optimizeAdLoading: true,
      }],
    ],
    android: {
      ...config.android,
      googleServicesFile: process.env.GOOGLE_SERVICES_JSON ?? config.android?.googleServicesFile,
    },
  };
};
