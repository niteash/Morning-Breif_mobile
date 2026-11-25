import { useCallback } from 'react';
import { router } from 'expo-router';
import { ArticleCard } from '../../components/ArticleCard';
import { Button, CircleButton, Notice, Screen, Type } from '../../components/ui/primitives';
import { Skeleton } from '../../components/ui/Skeleton';
import { getBookmarks } from '../../services/newsApi';
import { usePagedResource } from '../../hooks/usePagedResource';
import { useReadRefresh } from '../../hooks/useReadResource';
export default function SavedArticles() {
  const saved = usePagedResource(useCallback(async (offset: number) => { const result = await getBookmarks(offset); return { items: result.bookmarks.map(row => ({ ...row, id: row.article_id })), next_offset: result.next_offset }; }, []));
  useReadRefresh(saved.refresh);
  return <Screen><CircleButton label="နောက်သို့" onPress={() => router.canGoBack() ? router.back() : router.replace('/news')}>‹</CircleButton><Type variant="title">သိမ်းထားသော သတင်းများ</Type>
    <Notice message={saved.error} retry={() => void saved.refresh()} />
    {saved.loading && !saved.loaded ? <Skeleton /> : null}
    {saved.items.map(row => row.article ? <ArticleCard key={row.id} article={row.article} initialSaved onBookmarkChange={isSaved => { if (!isSaved) void saved.refresh(); }} /> : <Type key={row.id}>သတင်း မရရှိတော့ပါ။</Type>)}
    {saved.loaded && !saved.items.length ? <Type variant="muted">သိမ်းထားသော သတင်း မရှိသေးပါ။</Type> : null}
    {saved.next !== null ? <Button title="နောက်ထပ် ဖတ်မယ်" busy={saved.loading} onPress={() => void saved.more()} /> : null}
  </Screen>;
}
