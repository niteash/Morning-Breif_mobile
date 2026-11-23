import { useCallback, useState, type ReactNode } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { StyleSheet, Switch, View } from 'react-native';
import { usePreferences, usePalette } from '../../../features/preferences/PreferencesProvider';
import { NotificationPreferences } from '../../../components/NotificationPreferences';
import { TrialStatus } from '../../../components/TrialStatus';
import { AccountSettings } from '../../../components/AccountSettings';
import { ProfileSettings } from '../../../components/ProfileSettings';
import { useAccountId } from '../../../components/AuthGate';
import { registerForPushNotifications, signOutWithPushCleanup } from '../../../lib/pushNotifications';
import { getListeningSummary, updateMyPreferences } from '../../../services/userApi';
import { useBriefing } from '../../../features/playback/PlaybackProvider';
import { useReadRefresh, useReadResource } from '../../../hooks/useReadResource';
import { getEntitlement } from '../../../services/entitlementApi';
import { Button, Field, Loading, Notice, Panel, Screen, Type } from '../../../components/ui/primitives';
import { MotionPressable } from '../../../components/ui/Motion';

type SettingsSection = 'appearance' | 'schedule' | 'automation' | 'personalization' | 'listening' | 'notifications' | 'trial' | 'profile' | 'account';

const sectionTitles: Record<SettingsSection, string> = {
  appearance: 'ဘာသာစကားနှင့် ပုံစံ',
  schedule: 'နေ့စဉ် နားဆင်ချိန်',
  automation: 'အလိုအလျောက် ပြင်ဆင်မှု',
  personalization: 'ကိုယ်ပိုင် စိတ်ဝင်စားမှု',
  listening: 'နားဆင်မှုနှင့် ဒေတာ',
  notifications: 'အသိပေးချက်များ',
  trial: 'စမ်းသပ်ခွင့် အခြေအနေ',
  profile: 'ပရိုဖိုင်',
  account: 'အကောင့်နှင့် လုံခြုံရေး',
};

function isSection(value: string | undefined): value is SettingsSection {
  return Boolean(value && value in sectionTitles);
}

export default function SettingsScreen() {
  const accountId = useAccountId();
  const preferences = usePreferences();
  const colors = usePalette();
  const styles = makeStyles(colors);
  const params = useLocalSearchParams<{ section?: string | string[] }>();
  const rawSection = Array.isArray(params.section) ? params.section[0] : params.section;
  const section = isSection(rawSection) ? rawSection : null;
  const { profile, refresh, playback } = useBriefing();
  const entitlement = useReadResource(useCallback(() => getEntitlement(), []));
  const listeningSummary = useReadResource(useCallback(() => getListeningSummary(), []));
  const playbackActive = playback.playing || playback.intentPlaying;
  useReadRefresh(refresh);
  const [draftTime, setTime] = useState<string>();
  const [draftTimezone, setTimezone] = useState<string>();
  const [draftWeekendTime, setWeekendTime] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const time = draftTime ?? (profile.data ? `${String(profile.data.delivery_hour).padStart(2, '0')}:${String(profile.data.delivery_minute).padStart(2, '0')}` : '');
  const timezone = draftTimezone ?? profile.data?.timezone ?? '';
  const weekendTime = draftWeekendTime ?? (profile.data ? `${String(profile.data.weekend_delivery_hour ?? 8).padStart(2, '0')}:${String(profile.data.weekend_delivery_minute ?? 0).padStart(2, '0')}` : '');

  async function save() {
    if (busy || !profile.data) return;
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) {
      setError('၂၄ နာရီပုံစံဖြင့် အချိန်ထည့်ပါ။ ဥပမာ 06:30');
      return;
    }
    setBusy(true); setError(null); setMessage(null);
    try {
      const [delivery_hour, delivery_minute] = time.split(':').map(Number);
      await updateMyPreferences({ timezone: timezone.trim(), delivery_hour, delivery_minute });
      await profile.refresh();
      setMessage('ရွေးချယ်မှုများ သိမ်းပြီးပါပြီ။');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'သိမ်းဆည်းမရပါ။ ပြန်ကြိုးစားပါ။');
    } finally { setBusy(false); }
  }

  async function saveProfilePreference(data: {
    automatic_briefing_enabled?: boolean;
    daily_reminder_enabled?: boolean;
    auto_play_when_open?: boolean;
    delivery_schedule?: 'daily' | 'weekdays';
    weekend_delivery_hour?: number;
    weekend_delivery_minute?: number;
    separate_weekend_schedule?: boolean;
    briefing_length?: 'quick' | 'standard' | 'detailed';
    breaking_news_enabled?: boolean;
    data_saver_enabled?: boolean;
    auto_download_wifi?: boolean;
    listening_streak_enabled?: boolean;
    horoscope_sign?: 'aries' | 'taurus' | 'gemini' | 'cancer' | 'leo' | 'virgo' | 'libra' | 'scorpio' | 'sagittarius' | 'capricorn' | 'aquarius' | 'pisces' | null;
    crypto_watchlist?: ('BTC' | 'ETH' | 'SOL' | 'XRP' | 'BNB' | 'DOGE' | 'ADA' | 'AVAX' | 'DOT' | 'LINK')[];
  }) {
    const automaticRequested = ['automatic_briefing_enabled', 'daily_reminder_enabled', 'auto_play_when_open', 'delivery_schedule', 'weekend_delivery_hour', 'weekend_delivery_minute', 'separate_weekend_schedule']
      .some(key => key in data);
    if (busy || !profile.data || (automaticRequested && profile.data.automatic_delivery_preferences_available !== true)) {
      throw new Error('အလိုအလျောက်ပေးပို့မှုကို ဆာဗာတွင် မပြင်ဆင်ရသေးပါ။');
    }
    setBusy(true); setError(null); setMessage(null);
    try {
      if (data.daily_reminder_enabled) {
        const token = await registerForPushNotifications();
        if (!token) throw new Error('ဤဖုန်းတွင် အသိပေးချက် စာရင်းသွင်းမရပါ။');
      }
      await updateMyPreferences(data);
      await profile.refresh();
      setMessage('ရွေးချယ်မှုများ သိမ်းပြီးပါပြီ။');
    } catch (failure) {
      const detail = failure instanceof Error ? failure.message : 'သိမ်းဆည်းမရပါ။ ပြန်ကြိုးစားပါ။';
      setError(detail);
      throw failure;
    } finally { setBusy(false); }
  }

  async function signOut() {
    if (busy) return;
    setBusy(true); setError(null);
    try { await signOutWithPushCleanup(); router.replace('/sign-in'); }
    catch { setError('ထွက်မရသေးပါ။ ဤဖုန်းသို့ အသိပေးချက်များ ရပ်တန့်နိုင်ရန် အင်တာနက်ချိတ်ပြီး ပြန်ကြိုးစားပါ။'); }
    finally { setBusy(false); }
  }

  function open(next: SettingsSection) {
    setError(null); setMessage(null);
    router.push({ pathname: '/settings', params: { section: next } });
  }

  if (!section) {
    return <Screen contentContainerStyle={styles.screen}>
      <View style={styles.heading}>
        <Type variant="title">ဆက်တင်</Type>
        <Type variant="muted">ပြင်ဆင်လိုသော အပိုင်းကို ရွေးချယ်ပါ။</Type>
      </View>

      <SettingsGroup title="အက်ပ်">
        <SettingsRow icon="◐" title="ဘာသာစကားနှင့် ပုံစံ" detail="မြန်မာ၊ English၊ အလင်းနှင့် အမှောင်" onPress={() => open('appearance')} />
        <SettingsRow icon="◷" title="နေ့စဉ် နားဆင်ချိန်" detail={profile.data ? `${time} · ${timezone}` : 'အချိန်နှင့် စံတော်ချိန်'} onPress={() => open('schedule')} />
        <SettingsRow icon="⚙" title="အလိုအလျောက် ပြင်ဆင်မှု" detail={profile.data?.automatic_briefing_enabled ? 'ရွေးချယ်ထားသောအချိန်တွင် ဖွင့်ထားသည်' : 'ရွေးချယ်ထားသောအချိန်တွင် အလိုအလျောက်ပြင်ဆင်ရန်'} onPress={() => open('automation')} />
        <SettingsRow icon="◉" title="အသိပေးချက်များ" detail={profile.data?.daily_reminder_enabled ? 'နေ့စဉ် အသိပေးချက် ဖွင့်ထားသည်' : 'ခွင့်ပြုချက်နှင့် နေ့စဉ် အသိပေးချက်'} onPress={() => open('notifications')} last />
      </SettingsGroup>

      <SettingsGroup title="သတင်းနှင့် အသံ">
        <SettingsRow icon="✦" title="ကိုယ်ပိုင် စိတ်ဝင်စားမှု" detail="Crypto watchlist နှင့် ရာသီခွင်ကို ဦးစားပေးမယ်" onPress={() => open('personalization')} />
        <SettingsRow icon="♪" title="နားဆင်မှုနှင့် ဒေတာ" detail="အနှစ်ချုပ်ကြာချိန်၊ ဒေတာချွေတာမှုနှင့် အလိုအလျောက်သိမ်းမှု" onPress={() => open('listening')} />
        <SettingsRow icon="#" title="သတင်းကဏ္ဍများ" detail={playbackActive ? 'ကဏ္ဍပြောင်းရန် အသံကို အရင် ခေတ္တရပ်ပါ' : 'နောက်အနှစ်ချုပ်အတွက် စိတ်ဝင်စားသော ကဏ္ဍများ'} disabled={playbackActive} onPress={() => router.push('/category-preferences')} />
        <SettingsRow icon="↓" title="သိမ်းထားသော အသံများ" detail="အင်တာနက်မရှိချိန် နားဆင်ရန်" onPress={() => router.push('/downloads')} />
        <SettingsRow icon="↺" title="နားဆင်မှု မှတ်တမ်း" detail="ယခင် သတင်းအနှစ်ချုပ်များ" onPress={() => router.push('/history')} last />
      </SettingsGroup>

      <SettingsGroup title="အကောင့်">
        {accountId ? <SettingsRow icon="○" title="ပရိုဖိုင်" detail={profile.data?.name || 'ပုံ၊ အမည်နှင့် မိုဘိုင်းနံပါတ်'} onPress={() => open('profile')} /> : null}
        <SettingsRow icon="◇" title="စမ်းသပ်ခွင့် အခြေအနေ" detail="အသံပြင်ဆင်ခွင့်နှင့် သက်တမ်း" onPress={() => open('trial')} />
        <SettingsRow icon="⌾" title="အကောင့်နှင့် လုံခြုံရေး" detail="Google၊ အီးမေးလ်နှင့် အကောင့်ထွက်ရန်" onPress={() => open('account')} />
        <SettingsRow icon="§" title="ဥပဒေနှင့် အကူအညီ" detail="Privacy၊ Terms၊ Support နှင့် အကောင့်ဖျက်သိမ်းမှု" onPress={() => router.push('/legal')} last />
      </SettingsGroup>
      <Type variant="muted" style={styles.footer}>နေ့သစ် · YOUR PERSONAL NEWS APP</Type>
    </Screen>;
  }

  const needsProfile = ['schedule', 'automation', 'personalization', 'listening', 'notifications', 'profile'].includes(section);
  return <Screen keyboard contentContainerStyle={styles.screen}>
    <MotionPressable accessibilityRole="button" accessibilityLabel="ဆက်တင်စာရင်းသို့ ပြန်သွားမယ်" onPress={() => router.replace('/settings')} style={styles.backButton}>
      <Type variant="label" style={styles.backLabel}>←</Type>
      <Type variant="muted">ဆက်တင်</Type>
    </MotionPressable>
    <View style={styles.heading}>
      <Type variant="title">{sectionTitles[section]}</Type>
      <Type variant="muted">ဤအပိုင်းရှိ ရွေးချယ်မှုများကို ပြင်ဆင်ပါ။</Type>
    </View>

    {needsProfile && profile.loading && !profile.data ? <Loading /> : null}
    {needsProfile ? <Notice message={profile.error} retry={() => void profile.refresh()} /> : null}
    <Notice message={error} />
    {message ? <Type accessibilityLiveRegion="polite">{message}</Type> : null}

    {section === 'appearance' ? <Panel>
      <Type variant="label">ဘာသာစကား</Type>
      <View style={styles.choiceRow}>
        <View style={styles.choice}><Button title="မြန်မာ" secondary={preferences.language !== 'my'} onPress={() => void preferences.set({ language: 'my' })} /></View>
        <View style={styles.choice}><Button title="English" secondary={preferences.language !== 'en'} onPress={() => void preferences.set({ language: 'en' })} /></View>
      </View>
      <View style={styles.toggleRow}>
        <View style={styles.toggleCopy}>
          <Type variant="label">အမှောင်ပုံစံ</Type>
          <Type variant="muted">အက်ပ်၏ နောက်ခံနှင့် စာသားအရောင်ကို ပြောင်းပါ။</Type>
        </View>
        <Switch
          accessibilityLabel="အမှောင်ပုံစံ"
          accessibilityRole="switch"
          value={preferences.theme === 'dark'}
          onValueChange={enabled => void preferences.set({ theme: enabled ? 'dark' : 'light' })}
          trackColor={{ false: colors.border, true: colors.text }}
          thumbColor={preferences.theme === 'dark' ? colors.background : colors.surface}
        />
      </View>
      <Notice message={preferences.error ? 'ရွေးချယ်မှု သိမ်းမရပါ။ ပြန်ရွေးပါ။' : null} />
    </Panel> : null}

    {section === 'schedule' ? <Panel>
      <Field label="အချိန် (၂၄ နာရီပုံစံ)" value={time} onChangeText={setTime} editable={Boolean(profile.data) && !busy} placeholder="06:30" maxLength={5} />
      <Field label="စံတော်ချိန်" value={timezone} onChangeText={setTimezone} editable={Boolean(profile.data) && !busy} autoCapitalize="none" autoCorrect={false} placeholder="Asia/Yangon" />
      <Button title="သိမ်းမယ်" busy={busy} disabled={!profile.data || Boolean(profile.error)} onPress={save} />
      <Type variant="label">စနေ၊ တနင်္ဂနွေ</Type>
      <Field label="ပိတ်ရက်အချိန်" value={weekendTime} onChangeText={setWeekendTime} editable={Boolean(profile.data?.separate_weekend_schedule) && !busy} placeholder="08:00" maxLength={5} />
      <Button secondary disabled={!profile.data || profile.data.automatic_delivery_preferences_available !== true || busy} title={profile.data?.separate_weekend_schedule ? 'ပိတ်ရက် သီးသန့်အချိန် ပိတ်မယ်' : 'ပိတ်ရက် သီးသန့်အချိန် ဖွင့်မယ်'} onPress={() => void saveProfilePreference({ separate_weekend_schedule: !profile.data?.separate_weekend_schedule }).catch(() => {})} />
      {profile.data?.separate_weekend_schedule ? <Button secondary disabled={!/^([01]\d|2[0-3]):[0-5]\d$/.test(weekendTime) || busy} title="ပိတ်ရက်အချိန် သိမ်းမယ်" onPress={() => { const [weekend_delivery_hour, weekend_delivery_minute] = weekendTime.split(':').map(Number); void saveProfilePreference({ weekend_delivery_hour, weekend_delivery_minute }).catch(() => {}); }} /> : null}
    </Panel> : null}

    {section === 'automation' ? <Panel>
      <Type variant="label">အချိန်မီ သတင်းအနှစ်ချုပ်</Type>
      <Type variant="muted">သင်ရွေးချယ်ထားသောအချိန်ရောက်လျှင် နားဆင်ရန် အသင့်ဖြစ်နေစေရန် သတင်းနှင့်အသံကို ကြိုတင်ပြင်ဆင်ပါမည်။</Type>
      {profile.data?.automatic_delivery_preferences_available !== true ? <Type variant="muted">ဆာဗာနှင့် staging database ပြင်ဆင်ပြီးနောက် ဖွင့်နိုင်ပါမည်။</Type> : null}
      <Button disabled={!profile.data || profile.data.automatic_delivery_preferences_available !== true || busy || Boolean(profile.error)} title={profile.data?.automatic_briefing_enabled ? 'အလိုအလျောက် ပြင်ဆင်မှု ပိတ်မယ်' : 'အလိုအလျောက် ပြင်ဆင်မှု ဖွင့်မယ်'} onPress={() => void saveProfilePreference({ automatic_briefing_enabled: !profile.data?.automatic_briefing_enabled }).catch(() => {})} />
      <Button secondary disabled={!profile.data || profile.data.automatic_delivery_preferences_available !== true || busy || Boolean(profile.error)} title={profile.data?.delivery_schedule === 'weekdays' ? 'နေ့တိုင်း ပြောင်းမယ်' : 'အလုပ်ရက်များသာ ပြောင်းမယ်'} onPress={() => void saveProfilePreference({ delivery_schedule: profile.data?.delivery_schedule === 'weekdays' ? 'daily' : 'weekdays' }).catch(() => {})} />
      {process.env.EXPO_PUBLIC_AUTO_PLAY_ENABLED !== 'true' ? <Type variant="muted">အခြားအသံနှင့် မတော်တဆ အနှောင့်အယှက်မဖြစ်ကြောင်း Android တွင် စစ်ဆေးပြီးမှ ဖွင့်နိုင်ပါမည်။</Type> : null}
      <Button secondary disabled={!profile.data || profile.data.automatic_delivery_preferences_available !== true || busy || Boolean(profile.error) || (process.env.EXPO_PUBLIC_AUTO_PLAY_ENABLED !== 'true' && !profile.data.auto_play_when_open)} title={profile.data?.auto_play_when_open ? 'ဖွင့်ထားသောအခါ အလိုအလျောက်ဖွင့်မှု ပိတ်မယ်' : 'အက်ပ်ဖွင့်ထားသောအခါ အလိုအလျောက်ဖွင့်မယ်'} onPress={() => void saveProfilePreference({ auto_play_when_open: !profile.data?.auto_play_when_open }).catch(() => {})} />
      <Type variant="muted">အလိုအလျောက်ဖွင့်မှုသည် အက်ပ်ကို ဖွင့်ထားပြီး နားဆင်ချိန်ရောက်မှသာ လုပ်ဆောင်ပါမည်။</Type>
    </Panel> : null}

    {section === 'personalization' ? <Panel>
      <Type variant="label">Crypto watchlist</Type>
      <Type variant="muted">ရွေးထားသော coin ပါဝင်သည့် သတင်းကို အရင်စီမည်။ အခြားအရေးကြီးသတင်းများကို မဖျောက်ပါ။</Type>
      <View style={styles.wrapRow}>
        {(['BTC','ETH','SOL','XRP','BNB','DOGE','ADA','AVAX','DOT','LINK'] as const).map(symbol => {
          const selected = profile.data?.crypto_watchlist?.includes(symbol) === true;
          return <Button key={symbol} secondary={!selected} disabled={!profile.data || busy} title={symbol} onPress={() => {
            const current = profile.data?.crypto_watchlist ?? [];
            const crypto_watchlist = selected ? current.filter(item => item !== symbol) : [...current, symbol];
            void saveProfilePreference({ crypto_watchlist }).catch(() => {});
          }} />;
        })}
      </View>
      <Type variant="label">ရာသီခွင်</Type>
      <Type variant="muted">Horoscope ကို ဖျော်ဖြေရေးအဖြစ်သာ ဖော်ပြပြီး ကျန်းမာရေး၊ ငွေကြေး သို့မဟုတ် လုံခြုံရေးအကြံပြုချက်အဖြစ် မသုံးပါ။</Type>
      <View style={styles.wrapRow}>
        {(['aries','taurus','gemini','cancer','leo','virgo','libra','scorpio','sagittarius','capricorn','aquarius','pisces'] as const).map(sign => <Button
          key={sign} title={sign[0].toUpperCase() + sign.slice(1)}
          secondary={profile.data?.horoscope_sign !== sign} disabled={!profile.data || busy}
          onPress={() => void saveProfilePreference({ horoscope_sign: profile.data?.horoscope_sign === sign ? null : sign }).catch(() => {})}
        />)}
      </View>
    </Panel> : null}

    {section === 'listening' ? <Panel>
      <Type variant="label">ဒီအပတ် နားဆင်မှု</Type>
      {listeningSummary.data ? <Type translate={false} variant="muted">{preferences.language === 'my' ? `${listeningSummary.data.minutes} မိနစ် · အနှစ်ချုပ် ${listeningSummary.data.completed_briefings} ခု ပြီးဆုံး · ${listeningSummary.data.streak_days} ရက်ဆက်` : `${listeningSummary.data.minutes} min · ${listeningSummary.data.completed_briefings} briefings completed · ${listeningSummary.data.streak_days}-day streak`}</Type> : <Type variant="muted">နားဆင်ပြီးလျှင် ဒီနေရာတွင် အပတ်စဉ်မှတ်တမ်း ပြပါမည်။</Type>}
      <Type variant="label">အနှစ်ချုပ် ကြာချိန်</Type>
      <Type variant="muted">Quick ၃ မိနစ်၊ Standard ၇ မိနစ်၊ Detailed ၁၂–၁၅ မိနစ်</Type>
      <View style={styles.choiceRow}>
        {(['quick', 'standard', 'detailed'] as const).map(length => <View key={length} style={styles.choice}><Button
          title={length === 'quick' ? 'Quick' : length === 'standard' ? 'Standard' : 'Detailed'}
          secondary={profile.data?.briefing_length !== length} disabled={!profile.data || busy || (length !== 'standard' && entitlement.data?.entitlement_kind !== 'purchase')}
          onPress={() => void saveProfilePreference({ briefing_length: length }).catch(() => {})} /></View>)}
      </View>
      {entitlement.data?.entitlement_kind !== 'purchase' ? <Type variant="muted">Quick နှင့် Detailed သည် Premium အဖွဲ့ဝင်များအတွက် ဖြစ်ပါသည်။ Free တွင် Standard ၇ မိနစ် ရရှိပါသည်။</Type> : null}
      <Button secondary disabled={!profile.data || busy} title={profile.data?.data_saver_enabled ? 'ဒေတာချွေတာမှု ပိတ်မယ်' : 'ဒေတာချွေတာမှု ဖွင့်မယ်'} onPress={() => void saveProfilePreference({ data_saver_enabled: !profile.data?.data_saver_enabled }).catch(() => {})} />
      <Button secondary disabled={!profile.data || busy} title={profile.data?.auto_download_wifi ? 'Wi-Fi အလိုအလျောက်သိမ်းမှု ပိတ်မယ်' : 'Wi-Fi ဖြင့် အလိုအလျောက်သိမ်းမယ်'} onPress={() => void saveProfilePreference({ auto_download_wifi: !profile.data?.auto_download_wifi }).catch(() => {})} />
      <Button secondary disabled={!profile.data || busy} title={profile.data?.listening_streak_enabled ? 'နားဆင်ရက်ဆက် မှတ်တမ်း ပိတ်မယ်' : 'နားဆင်ရက်ဆက် မှတ်တမ်း ဖွင့်မယ်'} onPress={() => void saveProfilePreference({ listening_streak_enabled: !profile.data?.listening_streak_enabled }).catch(() => {})} />
      <Button secondary disabled={!profile.data || busy} title={profile.data?.breaking_news_enabled ? 'Breaking news အသိပေးချက် ပိတ်မယ်' : 'Breaking news အသိပေးချက် ဖွင့်မယ်'} onPress={() => void saveProfilePreference({ breaking_news_enabled: !profile.data?.breaking_news_enabled }).catch(() => {})} />
    </Panel> : null}

    {section === 'notifications' ? <NotificationPreferences enabled={profile.data?.daily_reminder_enabled === true} disabled={!profile.data || profile.data.automatic_delivery_preferences_available !== true || busy || Boolean(profile.error)} onToggle={enabled => saveProfilePreference({ daily_reminder_enabled: enabled })} /> : null}
    {section === 'trial' ? <TrialStatus /> : null}
    {section === 'profile' && profile.data ? <ProfileSettings profile={profile.data} refresh={profile.refresh} /> : null}
    {section === 'account' ? <>
      <AccountSettings />
      <Panel>
        <Type variant="label">အကောင့် လုပ်ဆောင်ချက်များ</Type>
        <Button secondary disabled={busy} title="အကောင့်မှ ထွက်မယ်" onPress={signOut} />
        <Button secondary disabled={busy} title="အကောင့် ဖျက်သိမ်းမယ်" onPress={() => router.push('/delete-account')} />
      </Panel>
    </> : null}
  </Screen>;
}

function SettingsGroup({ title, children }: { title: string; children: ReactNode }) {
  return <View style={{ gap: 9 }}>
    <Type variant="muted" style={{ fontSize: 12, letterSpacing: 1.6, paddingLeft: 4 }}>{title}</Type>
    <Panel style={{ padding: 0, gap: 0, overflow: 'hidden' }}>{children}</Panel>
  </View>;
}

function SettingsRow({ icon, title, detail, onPress, last = false, disabled = false }: { icon: string; title: string; detail: string; onPress: () => void; last?: boolean; disabled?: boolean }) {
  const colors = usePalette();
  const styles = makeStyles(colors);
  return <MotionPressable accessibilityRole="button" accessibilityLabel={`${title}။ ${detail}`} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.row, !last && styles.rowDivider, disabled && styles.rowDisabled, pressed && styles.rowPressed]}>
    <View style={styles.rowIcon}><Type translate={false} style={styles.rowIconText}>{icon}</Type></View>
    <View style={styles.rowCopy}>
      <Type variant="label">{title}</Type>
      <Type variant="muted" numberOfLines={2}>{detail}</Type>
    </View>
    <Type translate={false} style={styles.chevron}>›</Type>
  </MotionPressable>;
}

const makeStyles = (colors: ReturnType<typeof usePalette>) => StyleSheet.create({
  screen: { gap: 22 },
  heading: { gap: 3 },
  row: { minHeight: 78, paddingHorizontal: 20, paddingVertical: 13, flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: colors.surface },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowPressed: { backgroundColor: colors.border, opacity: 0.78 },
  rowDisabled: { opacity: 0.46 },
  rowCopy: { flex: 1, gap: 0 },
  rowIcon: { width: 38, height: 38, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
  rowIconText: { fontSize: 19, lineHeight: 24, color: colors.text },
  chevron: { color: colors.secondary, fontSize: 32, lineHeight: 36 },
  backButton: { alignSelf: 'flex-start', minHeight: 44, paddingHorizontal: 14, borderRadius: 22, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 8 },
  backLabel: { color: colors.text, fontSize: 22, lineHeight: 26 },
  choiceRow: { flexDirection: 'row', gap: 10 },
  choice: { flex: 1 },
  wrapRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  toggleRow: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: 16 },
  toggleCopy: { flex: 1, gap: 1 },
  footer: { textAlign: 'center', fontSize: 11, letterSpacing: 1.5, marginTop: 4 },
});
