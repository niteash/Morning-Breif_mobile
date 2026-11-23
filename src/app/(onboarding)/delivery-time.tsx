import { StepProgress, SunriseOrb } from '../../components/ui/SunriseMotion';
import { useCopy } from '../../features/preferences/PreferencesProvider';
import { useEffect, useState } from "react";
import { Platform, Pressable, View } from 'react-native';
import { Button, CircleButton, Field, Loading, Notice, Panel, Screen, Type } from '../../components/ui/primitives';
import DateTimePicker, {
  DateTimePickerEvent,
} from "@react-native-community/datetimepicker";

import { router, useLocalSearchParams } from "expo-router";

import {
  getOptionalPreferences,
  updateMyPreferences,
  updateMyCategories,
} from "../../services/userApi";
import { apiRequest } from '../../lib/api';

export default function DeliveryTimeScreen() {
  const t = useCopy();
  const { categories } = useLocalSearchParams<{
    categories?: string;
  }>();

  const [selectedTime, setSelectedTime] = useState(() => {
    const date = new Date();

    date.setHours(6);
    date.setMinutes(0);
    date.setSeconds(0);
    date.setMilliseconds(0);

    return date;
  });

  const [showPicker, setShowPicker] = useState(false);
  const [webDraft, setWebDraft] = useState<string>();

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [timezone, setTimezone] = useState("Asia/Yangon");
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);

  async function loadPreferences() {
    setLoading(true);
    setError(null);
    try {
      const profile = await getOptionalPreferences();
      if (profile) {
        setTimezone(profile.timezone);
        setSelectedTime((previous) => {
          const date = new Date(previous);
          date.setHours(profile.delivery_hour, profile.delivery_minute, 0, 0);
          return date;
        });
      }
      setLoaded(true);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to load preferences.");
    } finally { setLoading(false); }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadPreferences();
  }, []);

  const categoryIds =
    typeof categories === "string" ? categories.split(",").filter(Boolean) : [];

  // =========================================
  // Mobile DateTimePicker
  // =========================================

  function handleTimeChange(event: DateTimePickerEvent, selectedDate?: Date) {
    if (event.type === "dismissed") {
      setShowPicker(false);
      return;
    }

    setShowPicker(false);

    if (selectedDate) {
      setSelectedTime(selectedDate);
    }
  }

  // =========================================
  // Format selected time
  // =========================================

  function formatTime() {
    return selectedTime.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  }

  // =========================================
  // Web time input
  // =========================================

  function handleWebTimeChange(value: string) {
    setWebDraft(value);
    if (!value) {
      return;
    }

    const [hourString, minuteString] = value.split(":");

    const hour = Number(hourString);
    const minute = Number(minuteString);

    if (!Number.isInteger(hour) || !Number.isInteger(minute)) {
      return;
    }

    if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
      return;
    }

    const newTime = new Date(selectedTime);

    newTime.setHours(hour);
    newTime.setMinutes(minute);
    newTime.setSeconds(0);
    newTime.setMilliseconds(0);

    setSelectedTime(newTime);
  }

  // =========================================
  // Save onboarding
  // =========================================

  async function handleContinue() {
    if (saving || !loaded) {
      return;
    }

    let preferencesSaved = false;
    try {
      setSaving(true);
      setError(null);

      if (Platform.OS === 'web' && webDraft !== undefined && !/^([01]\d|2[0-3]):[0-5]\d$/.test(webDraft)) {
        throw new Error('၂၄ နာရီပုံစံဖြင့် အချိန်ထည့်ပါ။ ဥပမာ 06:30');
      }

      if (categoryIds.length === 0) {
        throw new Error("No categories were selected.");
      }

      const deliveryHour = selectedTime.getHours();

      const deliveryMinute = selectedTime.getMinutes();

      // =====================================
      // Save delivery time
      // =====================================

      await updateMyPreferences({
        timezone,
        delivery_hour: deliveryHour,
        delivery_minute: deliveryMinute,
      });


      // =====================================
      // Save selected categories
      // =====================================

      preferencesSaved = true;
      await updateMyCategories(categoryIds);
      // Trial claim is independent and retryable; onboarding remains saved on outage.
      try { await apiRequest('/api/v1/entitlements/claim', { method: 'POST' }); }
      catch { router.navigate({ pathname: '/home', params: { trialClaimRetry: '1' } }); return; }



      // =====================================
      // Go to Home
      // =====================================

      router.navigate("/home");
    } catch (error) {
      setError((preferencesSaved ? "အချိန်ကို သိမ်းပြီးပါပြီ။ ကဏ္ဍများ သိမ်းမရသေးပါ။ ပြန်ကြိုးစားပါ။ " : "") + (error instanceof Error ? error.message : "သိမ်းဆည်းမရပါ။ ပြန်ကြိုးစားပါ။"));
    } finally {
      setSaving(false);
    }
  }

  // =========================================
  // Web time value
  // =========================================

  const webTimeValue = `${String(selectedTime.getHours()).padStart(
    2,
    "0",
  )}:${String(selectedTime.getMinutes()).padStart(2, "0")}`;

  return <Screen keyboard>
    <CircleButton label="ကဏ္ဍများ ပြန်ရွေးမယ်" disabled={saving} onPress={() => router.canGoBack() ? router.back() : router.replace('/categories')}>‹</CircleButton>
    <StepProgress step={3} />
    <SunriseOrb size={140} />
    <Type variant="muted">နေ့သစ် · နားဆင်ချိန်</Type>
    <Type variant="hero">ဘယ်အချိန်မှာ နားဆင်ချင်လဲ?</Type>
    <Type variant="muted">သင်ရွေးထားသည့် အချိန်အတွက် နေ့စဉ်အနှစ်ချုပ်ကို ပြင်ဆင်ပေးပါမည်။</Type>
    {loading ? <Loading /> : null}<Notice message={error} retry={!loaded && !loading ? loadPreferences : undefined} />
    <Panel>
      <Type variant="label">နေ့စဉ် ရယူမည့်အချိန်</Type>
      {Platform.OS !== 'web' ? <Pressable accessibilityRole="button" accessibilityLabel={t('နေ့စဉ် ရယူမည့်အချိန် ပြောင်းမယ်')} disabled={saving || !loaded} onPress={() => setShowPicker(true)} style={{ minHeight: 80, justifyContent: 'center' }}><Type variant="hero">{formatTime()}</Type><Type variant="muted">အချိန်ပြောင်းရန် နှိပ်ပါ</Type></Pressable> : <Field label="အချိန် (HH:mm)" value={webDraft ?? webTimeValue} editable={loaded && !saving} onChangeText={handleWebTimeChange} placeholder="06:00" maxLength={5} />}
      <Type variant="muted">စံတော်ချိန် · {timezone}</Type>
      <Field label="စံတော်ချိန် (IANA)" value={timezone} onChangeText={setTimezone} editable={loaded && !saving} autoCapitalize="none" placeholder="Asia/Yangon" />
    </Panel>
    {Platform.OS !== 'web' && showPicker ? <DateTimePicker value={selectedTime} mode="time" display="spinner" onChange={handleTimeChange} /> : null}
    <Panel><Type variant="label">ရွေးချယ်ထားသော ကဏ္ဍ {categoryIds.length} ခု</Type><Type variant="muted">ကဏ္ဍအားလုံးကို အသံအနှစ်ချုပ် တစ်ခုတည်းအဖြစ် နားဆင်နိုင်ပါမည်။</Type></Panel>
    <View style={{ gap: 12 }}><Button title="သိမ်းပြီး ဆက်လုပ်မယ်" busy={saving} disabled={!loaded} onPress={handleContinue} /></View>
  </Screen>;
}
