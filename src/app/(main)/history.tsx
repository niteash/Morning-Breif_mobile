import { useCallback, useEffect, useRef, useState } from 'react';
import { router } from 'expo-router';
import { getBriefingHistory, getHistoricalBriefing } from '../../services/briefingApi';
import { usePagedResource } from '../../hooks/usePagedResource';
import { useBriefing } from '../../features/playback/PlaybackProvider';
import { Button, CircleButton, Notice, Panel, Screen, Type } from '../../components/ui/primitives';
import { Skeleton } from '../../components/ui/Skeleton';
export default function HistoryScreen() {
  const { controller } = useBriefing();
  const [opening, setOpening] = useState<string | null>(null), [error, setError] = useState<string | null>(null);
  const history = usePagedResource(useCallback(async (offset: number) => {
    const page = await getBriefingHistory(offset); return { items: page.briefings, next_offset: page.next_offset };
  }, []));
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function open(id: string) {
    if (opening) return;
    setOpening(id); setError(null);
    try {
      const { briefing } = await getHistoricalBriefing(id);
      if (briefing.status !== 'ready' || !briefing.audio_url) throw Error('အသံဖိုင် မရရှိသေးပါ။');
      await controller.select(briefing, false, true);
      if (mounted.current) router.push('/player');
    } catch { setError('အနှစ်ချုပ် ဖွင့်မရပါ။ အင်တာနက်ကိုစစ်ပြီး ပြန်ကြိုးစားပါ။'); }
    finally { setOpening(null); }
  }
  return <Screen>
    <CircleButton label="နောက်သို့" onPress={() => router.canGoBack() ? router.back() : router.replace('/home')}>‹</CircleButton>
    <Type variant="title">နားဆင်မှု မှတ်တမ်း</Type>
    <Notice message={history.error} retry={() => void history.refresh()} /><Notice message={error} />
    {history.loading && !history.loaded ? <Skeleton /> : null}
    {history.loaded && !history.items.length ? <Type>သိမ်းထားသော အနှစ်ချုပ် မရှိသေးပါ။</Type> : null}
    {history.items.map(item => <Panel key={item.id}><Type variant="muted">{item.briefing_date}</Type><Type translate={false} variant="label">{item.title}</Type><Type variant="muted">{item.status}</Type><Button title="အနှစ်ချုပ် ဖွင့်မယ်" disabled={item.status !== 'ready' || Boolean(opening)} busy={opening === item.id} onPress={() => void open(item.id)} /></Panel>)}
    {history.next !== null ? <Button secondary title="နောက်ထပ် ဖတ်မယ်" busy={history.loading} onPress={() => void history.more()} /> : null}
  </Screen>;
}
