import { useCallback, useEffect, useState } from 'react';
import { router } from 'expo-router';
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { ArticleCard } from '../../../components/ArticleCard';
import { Button, Field, Notice, Panel, Screen, Type } from '../../../components/ui/primitives';
import { Skeleton } from '../../../components/ui/Skeleton';
import { discoverNews } from '../../../services/newsApi';
import { getTodayBriefing } from '../../../services/briefingApi';
import { useReadRefresh, useReadResource } from '../../../hooks/useReadResource';
import { usePagedResource } from '../../../hooks/usePagedResource';
import { usePalette, usePreferences } from '../../../features/preferences/PreferencesProvider';
import { getMyCategories } from '../../../services/userApi';
import { MotionPressable, Reveal } from '../../../components/ui/Motion';
export default function NewsScreen() {
  const colors = usePalette(), { language } = usePreferences();
  const [category, setCategory] = useState<string>(), [input, setInput] = useState(''), [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  useEffect(() => { const timer = setTimeout(() => setQuery(input.trim()), 300); return () => clearTimeout(timer); }, [input]);
  const interests = useReadResource(useCallback(() => getMyCategories(), []));
  const ranked = useReadResource(useCallback(() => getTodayBriefing(), []));
  const latest = usePagedResource(useCallback(async (offset: number) => {
    const page = await discoverNews({ q: query, category_id: category, offset, selected_only: true });
    return { items: page.news, next_offset: page.next_offset };
  }, [query, category]));
  const refreshInterests = interests.refresh, refreshLatest = latest.refresh, refreshRanked = ranked.refresh;
  useReadRefresh(useCallback(() => {
    void refreshInterests(false); void refreshLatest(); void refreshRanked(false);
  }, [refreshInterests, refreshLatest, refreshRanked]));
  const selected = interests.data?.categories
    .filter(item => item.categories)
    .map(item => ({ ...item.categories!, id: item.category_id })) || [];
  const selectedIds = new Set(selected.map(item => item.id));
  const visibleRanked = ranked.data?.categories.filter(group => selectedIds.has(group.category.id)) || [];
  return <Screen refreshControl={<RefreshControl refreshing={latest.loading && latest.loaded} onRefresh={() => { void latest.refresh(); void ranked.refresh(); void interests.refresh(); }} />}>
    <View style={styles.header}>
      <Type variant="title" style={{ flex: 1 }}>သတင်းများ</Type>
      <NewsIconButton icon="☆" label="သိမ်းထားသော သတင်းများ" onPress={() => router.push('/saved-articles')} />
      <NewsIconButton icon="⌕" label="သတင်း ရှာဖွေမယ်" selected={searchOpen} onPress={() => setSearchOpen(value => !value)} />
    </View>
    <Type variant="muted">သင်ရွေးချယ်ထားသော ကဏ္ဍများမှ သတင်းများကိုသာ ပြထားပါသည်။</Type>
    {searchOpen ? <Reveal><Field label="သတင်း ရှာဖွေမယ်" value={input} onChangeText={setInput} maxLength={120} autoFocus autoCorrect={false} returnKeyType="search" onSubmitEditing={() => setQuery(input.trim())} /></Reveal> : null}
    <Notice message={interests.error} retry={() => void interests.refresh()} />
    <View style={{ gap: 8 }}>
      <Type variant="label">သင့်သတင်းကဏ္ဍများ</Type>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingRight: 24 }}>
        {[{ id: undefined, name_my: 'ကျွန်ုပ်၏ သတင်းအားလုံး', name_en: 'All my news' }, ...selected].map(item => <Pressable key={item.id || 'selected-all'} accessibilityRole="radio" accessibilityState={{ checked: category === item.id }} onPress={() => setCategory(item.id)} style={{ minHeight: 48, borderRadius: 24, paddingHorizontal: 18, paddingVertical: 10, justifyContent: 'center', backgroundColor: category === item.id ? colors.text : colors.surface, borderWidth: 1, borderColor: colors.border }}><Type style={{ color: category === item.id ? colors.surface : colors.text }}>{language === 'my' ? item.name_my : item.name_en}</Type></Pressable>)}
      </ScrollView>
    </View>
    {!interests.loading && !interests.error && !selected.length ? <Panel><Type>သတင်းကဏ္ဍ မရွေးရသေးပါ။ ဆက်တင်တွင် အရင်ရွေးပါ။</Type><Button title="သတင်းကဏ္ဍ ရွေးမယ်" onPress={() => router.push('/category-preferences')} /></Panel> : null}
    {!query && !category ? <><Type variant="label">ယခု ရွေးချယ်ထားသော သတင်းများ</Type><Notice message={ranked.error} retry={() => void ranked.refresh()} />
      {visibleRanked.map(group => <View key={group.category.id} style={{ gap: 12 }}><Type variant="label">{language === 'my' ? group.category.name_my : group.category.name_en}</Type>{group.stories.slice(0, 2).map(article => <ArticleCard key={article.id} article={article} compact />)}</View>)}
    </> : null}
    <Type variant="label">နောက်ဆုံးရရှိသော သတင်းများ</Type>
    <Notice message={latest.error} retry={() => void latest.refresh()} />
    {latest.loading && !latest.loaded ? <Skeleton /> : null}
    {latest.items.map(article => <ArticleCard key={article.id} article={article} />)}
    {latest.loaded && !latest.items.length ? <><Type variant="muted">သတင်း မရရှိသေးပါ။</Type><Button secondary title="ပြန်ကြိုးစားမယ်" onPress={() => void latest.refresh()} /></> : null}
    {latest.next !== null ? <Button secondary title="နောက်ထပ် ဖတ်မယ်" busy={latest.loading} onPress={() => void latest.more()} /> : null}
  </Screen>;
}

function NewsIconButton({ icon, label, onPress, selected = false }: { icon: string; label: string; onPress: () => void; selected?: boolean }) {
  const colors = usePalette();
  return <MotionPressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected, expanded: label === 'သတင်း ရှာဖွေမယ်' ? selected : undefined }} onPress={onPress} style={({ pressed }) => [styles.iconButton, { backgroundColor: selected ? colors.text : colors.surface, borderColor: selected ? colors.text : colors.border }, pressed && { opacity: 0.65 }]}>
    <Type translate={false} style={{ color: selected ? colors.surface : colors.text, fontSize: 22, lineHeight: 25 }}>{icon}</Type>
  </MotionPressable>;
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  iconButton: { width: 48, height: 48, borderRadius: 17, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
});
