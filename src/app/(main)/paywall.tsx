import { useEffect, useState } from 'react';
import { router } from 'expo-router';
import type { PurchasesPackage } from 'react-native-purchases';
import { Button, CircleButton, Notice, Panel, Screen, Type } from '../../components/ui/primitives';
import { TrialStatus } from '../../components/TrialStatus';
import { buyPackage, loadPurchaseOptions, purchaseWasCancelled, restorePurchaseAccess } from '../../lib/purchases';

export default function PaywallScreen() {
  const [packages, setPackages] = useState<PurchasesPackage[]>([]);
  const [busy, setBusy] = useState<string | null>('load');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy('load'); setError(null);
    try { setPackages(await loadPurchaseOptions()); }
    catch { setError('ဝယ်ယူမှုအစီအစဉ်များကို ရယူမရပါ။ နောက်မှ ပြန်ကြိုးစားပါ။'); }
    finally { setBusy(null); }
  }
  useEffect(() => {
    let active = true;
    void loadPurchaseOptions()
      .then(items => { if (active) setPackages(items); })
      .catch(() => { if (active) setError('ဝယ်ယူမှုအစီအစဉ်များကို ရယူမရပါ။ နောက်မှ ပြန်ကြိုးစားပါ။'); })
      .finally(() => { if (active) setBusy(null); });
    return () => { active = false; };
  }, []);

  async function purchase(aPackage: PurchasesPackage) {
    setBusy(aPackage.identifier); setError(null); setMessage(null);
    try {
      const active = await buyPackage(aPackage);
      setMessage(active ? 'ဝယ်ယူမှု အောင်မြင်ပါသည်။' : 'ငွေပေးချေမှုကို စစ်ဆေးနေဆဲဖြစ်သည်။ ခဏအကြာ ပြန်စစ်ပါ။');
    } catch (caught) {
      if (!purchaseWasCancelled(caught)) setError('ဝယ်ယူမှု မပြီးမြောက်ပါ။ ငွေပေးချေမှုအခြေအနေကို စစ်ပြီး ပြန်ကြိုးစားပါ။');
    } finally { setBusy(null); }
  }

  async function restore() {
    setBusy('restore'); setError(null); setMessage(null);
    try { setMessage(await restorePurchaseAccess() ? 'ယခင်ဝယ်ယူမှုကို ပြန်လည်ရရှိပါပြီ။' : 'ပြန်လည်ရယူနိုင်သော ဝယ်ယူမှု မတွေ့ပါ။'); }
    catch { setError('ယခင်ဝယ်ယူမှုကို ပြန်လည်ရယူမရပါ။ ပြန်ကြိုးစားပါ။'); }
    finally { setBusy(null); }
  }

  return <Screen>
    <CircleButton label="နောက်သို့" disabled={busy !== null} onPress={() => router.canGoBack() ? router.back() : router.replace('/home')}>‹</CircleButton>
    <Type variant="title">အသံသတင်း အစီအစဉ်</Type>
    <TrialStatus />
    <Notice message={error} retry={() => void load()} />
    {message ? <Panel><Type accessibilityLiveRegion="polite">{message}</Type></Panel> : null}
    {packages.map(item => <Panel key={item.identifier}>
      <Type variant="label">{item.product.title}</Type>
      <Type variant="muted">{item.product.description}</Type>
      <Button title={`${item.product.priceString} · ဝယ်ယူမယ်`} busy={busy === item.identifier} disabled={busy !== null} onPress={() => void purchase(item)} />
    </Panel>)}
    <Button secondary title="ယခင်ဝယ်ယူမှု ပြန်ယူမယ်" busy={busy === 'restore'} disabled={busy !== null} onPress={() => void restore()} />
  </Screen>;
}
