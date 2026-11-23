import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

const AdsReadyContext = createContext(false);

export function AdsProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (process.env.EXPO_PUBLIC_ADS_ENABLED !== 'true') return;
    let active = true;
    void import('react-native-google-mobile-ads').then(async ads => {
      // Fail closed: no ad request is made until the platform consent flow says
      // it is allowed. Development and production use the same privacy gate.
      const consent = await ads.AdsConsent.gatherConsent({ tagForUnderAgeOfConsent: false });
      if (!active || !consent.canRequestAds) return;
      await ads.default().initialize();
      if (active) setReady(true);
    }).catch(() => {
      // Ads are optional revenue UI; failures must never block the news app.
      if (active) setReady(false);
    });
    return () => { active = false; };
  }, []);

  return <AdsReadyContext.Provider value={ready}>{children}</AdsReadyContext.Provider>;
}

export function useAdsReady() {
  return useContext(AdsReadyContext);
}
