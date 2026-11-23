import { Linking } from 'react-native';
import { router } from 'expo-router';
import { Button, CircleButton, Panel, Screen, Type } from '../../components/ui/primitives';

const legalBase = (process.env.EXPO_PUBLIC_LEGAL_BASE_URL || '').replace(/\/$/, '');

export default function LegalScreen() {
  const open = (path: string) => legalBase ? void Linking.openURL(`${legalBase}/${path}`) : undefined;
  return <Screen>
    <CircleButton label="နောက်သို့" onPress={() => router.canGoBack() ? router.back() : router.replace('/settings')}>‹</CircleButton>
    <Type variant="title">ဥပဒေနှင့် အကူအညီ</Type>
    <Panel>
      <Type variant="label">ကိုယ်ရေးအချက်အလက်</Type>
      <Type variant="muted">အကောင့်၊ သတင်းရွေးချယ်မှု၊ နားဆင်မှတ်တမ်းနှင့် စက်အသိပေး token များကို အက်ပ်ဝန်ဆောင်မှုပေးရန်သာ အသုံးပြုပါသည်။ ကြော်ငြာနှင့် ဝယ်ယူမှု SDK များ၏ ဒေတာအသုံးပြုမှုကို ထုတ်ဝေထားသော policy တွင် ဖော်ပြထားပါသည်။</Type>
      <Button secondary disabled={!legalBase} title="Privacy Policy အပြည့်အစုံ" onPress={() => open('privacy.html')} />
    </Panel>
    <Panel>
      <Type variant="label">အသုံးပြုမှု စည်းကမ်း</Type>
      <Type variant="muted">သတင်းအနှစ်ချုပ်များသည် AI ဖြင့် ပြင်ဆင်ထားပြီး မူရင်းသတင်းထုတ်ဝေသူ၏ စာမျက်နှာကို အတည်ပြုဖတ်ရှုနိုင်ပါသည်။ အရေးကြီးဆုံးဖြတ်ချက်များအတွက် အနှစ်ချုပ်တစ်ခုတည်းကို မမှီခိုပါနှင့်။</Type>
      <Button secondary disabled={!legalBase} title="Terms အပြည့်အစုံ" onPress={() => open('terms.html')} />
    </Panel>
    <Panel>
      <Type variant="label">အကူအညီနှင့် အကောင့်ဖျက်သိမ်းမှု</Type>
      <Button secondary title="အကောင့်ဖျက်သိမ်းမယ်" onPress={() => router.push('/delete-account')} />
      <Button secondary disabled={!legalBase} title="Support စာမျက်နှာ" onPress={() => open('support.html')} />
    </Panel>
  </Screen>;
}
