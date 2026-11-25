import { useEffect, useRef, useState } from 'react';
import { router } from 'expo-router';
import { useOfflineAudio } from '../../hooks/useOfflineAudio';
import { useBriefing } from '../../features/playback/PlaybackProvider';
import { Button, CircleButton, Notice, Panel, Screen, Type } from '../../components/ui/primitives';
export default function DownloadsScreen() {
  const offline = useOfflineAudio(), { controller, playback } = useBriefing();
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function open(id: string) {
    try { const record = await offline.open(id); await controller.select(record, true, true); if (mounted.current) router.push('/player'); }
    catch { setError('အသံဖိုင် မရရှိသေးပါ။ ပြန်လည်စစ်ဆေးပါ။'); }
  }
  return <Screen><CircleButton label="နောက်သို့" onPress={() => router.canGoBack() ? router.back() : router.replace('/home')}>‹</CircleButton>
    <Type variant="title">သိမ်းထားသော အသံများ</Type>
    <Type variant="muted">အသံများကို ၇ ရက်၊ ၅ ဖိုင်အထိ ဤအကောင့်အတွက် သိမ်းနိုင်သည်။ ဖုန်းက နေရာလွတ်လိုလျှင် ဖျက်နိုင်သည်။ အကောင့်ထွက်လျှင် ဖျက်မည်။</Type>
    <Type variant="muted">အက်ပ်ကို အသစ်ဖွင့်ရာတွင် အကောင့်နှင့် စတင်ပြင်ဆင်မှု စစ်ရန် အင်တာနက်လိုအပ်သည်။</Type>
    <Notice message={offline.downloads.error || offline.error || error} retry={() => void offline.downloads.refresh()} />
    {offline.downloads.data?.length === 0 ? <Type>သိမ်းထားသော အသံ မရှိသေးပါ။</Type> : null}
    {offline.downloads.data?.map(item => <Panel key={item.id}><Type>{item.briefing_date}</Type><Button title="နားဆင်မယ်" onPress={() => void open(item.id)} /><Button secondary title="သိမ်းထားမှု ဖယ်မယ်" busy={offline.busy} disabled={playback.record?.id === item.id && playback.record.offline} onPress={() => void offline.remove(item.id)} /></Panel>)}
  </Screen>;
}
