import { lazy, Suspense, useCallback } from 'react';
import { useAdsReady } from '../../features/ads/AdsProvider';
import { useReadResource } from '../../hooks/useReadResource';
import { getEntitlement } from '../../services/entitlementApi';

const NativeBanner = lazy(async () => ({
  default: (await import('./SponsoredBannerNative')).SponsoredBannerNative,
}));

export function SponsoredBanner() {
  const ready = useAdsReady();
  const entitlement = useReadResource(useCallback(() => getEntitlement(), []));
  if (!ready || process.env.EXPO_PUBLIC_ADS_ENABLED !== 'true' || entitlement.data?.entitlement_kind === 'purchase') return null;
  // Keep the native module out of existing development clients when ads are
  // disabled. Enabling ads requires a fresh native development/production build.
  return <Suspense fallback={null}><NativeBanner /></Suspense>;
}
