import { useState } from 'react';
import { View } from 'react-native';
import { BannerAd, BannerAdSize, TestIds } from 'react-native-google-mobile-ads';
import { Panel, Type } from '../ui/primitives';

export function SponsoredBannerNative() {
  const [available, setAvailable] = useState(true);
  const unitId = __DEV__ ? TestIds.BANNER : process.env.EXPO_PUBLIC_ADMOB_BANNER_UNIT_ID;
  if (!available || !unitId) return null;

  return <Panel style={{ padding: 14, gap: 8, alignItems: 'center' }}>
    <Type translate={false} variant="muted" style={{ alignSelf: 'flex-start', fontSize: 10, letterSpacing: 1.8 }}>SPONSORED</Type>
    <View style={{ minHeight: 50, alignItems: 'center', justifyContent: 'center' }}>
      <BannerAd
        unitId={unitId}
        size={BannerAdSize.BANNER}
        requestOptions={{ requestNonPersonalizedAdsOnly: false }}
        onAdFailedToLoad={() => setAvailable(false)}
      />
    </View>
  </Panel>;
}
