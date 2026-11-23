import { MotionPressable, Reveal } from '../../components/ui/Motion';
import { StepProgress, SunriseOrb } from '../../components/ui/SunriseMotion';
import { useCallback, useEffect, useState } from "react";
import { View } from 'react-native';
import { Button, Loading, Notice, Screen, Type } from '../../components/ui/primitives';
import { usePalette, usePreferences } from '../../features/preferences/PreferencesProvider';
import { router, useFocusEffect } from "expo-router";
import { getCategories } from "../../services/categoryApi";

import { getMyCategories } from "../../services/userApi";

type Category = {
  id: string;
  slug: string;
  name_en: string;
  name_my: string;
  active: boolean;
};

export default function CategoriesScreen() {
  const colors = usePalette(), { language } = usePreferences();
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [navigating, setNavigating] = useState(false);


  async function loadCategories() {
    try {
      setLoading(true);
      setError(null);

      const [response, saved] = await Promise.all([getCategories(), getMyCategories()]);
      const available = response.categories as Category[];
      setCategories(available);
      setSelectedCategories(saved.categories.map((item) => item.category_id)
        .filter((id) => available.some((category) => category.id === id)));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to load categories.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Begin the initial network request; loading is already true.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCategories();
  }, []);

  useFocusEffect(useCallback(() => {
    setNavigating(false);
  }, []));

  function toggleCategory(categoryId: string) {
    if (navigating) return;

    setSelectedCategories((current) => {
      if (current.includes(categoryId)) {
        return current.filter((id) => id !== categoryId);
      }

      return [...current, categoryId];
    });
  }

  function handleContinue() {
    if (navigating) {
      return;
    }

    if (selectedCategories.length === 0) {
      return;
    }


    setNavigating(true);

    const categoryParam = selectedCategories.join(",");


    router.push({
      pathname: "/delivery-time",
      params: {
        categories: categoryParam,
      },
    });
  }

  if (loading) return <Screen><Loading label="ကဏ္ဍများကို ရယူနေသည်…" /></Screen>;
  return <Screen>
    <StepProgress step={2} />
    <SunriseOrb size={110} />
    <Type variant="muted">နေ့သစ် · သင့်စိတ်ဝင်စားမှုများ</Type>
    <Type variant="hero">ဘာတွေကို သိချင်လဲ?</Type>
    <Type variant="muted">သင်နားဆင်လိုသော သတင်းကဏ္ဍများကို ရွေးချယ်ပါ။ နောက်တစ်ဆင့်တွင် သိမ်းဆည်းပါမည်။</Type>
    <Notice message={error} retry={loadCategories} />
    {!error && categories.length === 0 ? <Type variant="muted">ရွေးချယ်ရန် ကဏ္ဍ မရရှိသေးပါ။</Type> : null}
    {categories.map((category, index) => {
      const selected = selectedCategories.includes(category.id);
      return <Reveal key={category.id} delay={index * 40}><MotionPressable accessibilityRole="checkbox" accessibilityState={{ checked: selected, disabled: navigating }} disabled={navigating} onPress={() => toggleCategory(category.id)} style={{ backgroundColor: colors.surface, borderWidth: selected ? 2 : 1, borderColor: selected ? colors.text : colors.border, borderRadius: 18, padding: 22, minHeight: 88, flexDirection: 'row', alignItems: 'center', gap: 16 }}>
        <View style={{ flex: 1 }}><Type variant="label" style={{ fontSize: 20 }}>{language === 'my' ? category.name_my : category.name_en}</Type><Type variant="muted">{language === 'my' ? category.name_en : category.name_my}</Type></View>
        <View style={{ width: 28, height: 28, borderRadius: 14, borderWidth: 1, borderColor: colors.text, backgroundColor: selected ? colors.text : colors.surface, alignItems: 'center', justifyContent: 'center' }}><Type style={{ color: colors.surface, fontSize: 16, lineHeight: 24 }}>{selected ? '✓' : ''}</Type></View>
      </MotionPressable></Reveal>;
    })}
    <Button title="ဆက်လုပ်မယ်" busy={navigating} disabled={Boolean(error) || !selectedCategories.length} onPress={handleContinue} />
  </Screen>;
}
