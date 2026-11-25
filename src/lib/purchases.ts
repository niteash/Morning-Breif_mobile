import { Platform } from 'react-native';
import Purchases, { type CustomerInfo, type PurchasesPackage } from 'react-native-purchases';
import { ensureAuthenticated } from './auth';

const ENTITLEMENT_ID = process.env.EXPO_PUBLIC_REVENUECAT_ENTITLEMENT_ID || 'premium';
let configured = false;

function publicApiKey(): string {
  const key = Platform.OS === 'ios'
    ? process.env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY
    : Platform.OS === 'android'
      ? process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY
      : undefined;
  if (!key) throw new Error('Purchases are not configured for this build.');
  return key;
}

async function ensurePurchaseIdentity(): Promise<string> {
  const session = await ensureAuthenticated();
  if (Platform.OS !== 'android' && Platform.OS !== 'ios') {
    throw new Error('Purchases are available in the Android and iOS apps.');
  }
  if (!configured && !(await Purchases.isConfigured())) {
    Purchases.configure({ apiKey: publicApiKey(), appUserID: session.user.id });
    configured = true;
  } else {
    configured = true;
    if (await Purchases.getAppUserID() !== session.user.id) {
      await Purchases.logIn(session.user.id);
    }
  }
  return session.user.id;
}

export function hasPremiumAccess(info: CustomerInfo): boolean {
  return info.entitlements.active[ENTITLEMENT_ID]?.isActive === true;
}

export async function loadPurchaseOptions(): Promise<PurchasesPackage[]> {
  await ensurePurchaseIdentity();
  const offering = (await Purchases.getOfferings()).current;
  if (!offering?.availablePackages.length) throw new Error('No purchase plans are available.');
  return offering.availablePackages;
}

export async function buyPackage(aPackage: PurchasesPackage): Promise<boolean> {
  await ensurePurchaseIdentity();
  return hasPremiumAccess((await Purchases.purchasePackage(aPackage)).customerInfo);
}

export async function restorePurchaseAccess(): Promise<boolean> {
  await ensurePurchaseIdentity();
  return hasPremiumAccess(await Purchases.restorePurchases());
}

export function purchaseWasCancelled(error: unknown): boolean {
  return Boolean(error && typeof error === 'object' && 'userCancelled' in error && error.userCancelled);
}
