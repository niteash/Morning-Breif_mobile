import { useEffect, useRef, useState } from "react";
import { Button, CircleButton, Field, Loading, Notice, Panel, Screen, Type } from "../components/ui/primitives";
import { router } from "expo-router";
import { apiRequest } from "../lib/api";
import { ensureAuthenticated } from "../lib/auth";
import { supabase } from "../lib/supabase";
import { submitAccountDeletion } from "../lib/accountDeletion";

// Outside the main layout: pending deletion must remain reachable when profile access is denied.
export default function DeleteAccountScreen() {
  const [confirmation, setConfirmation] = useState("");
  const [account, setAccount] = useState<{ id: string; enabled: boolean; requested: boolean }>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [reauthenticate, setReauthenticate] = useState(false);
  const working = useRef(false);

  async function load() {
    if (working.current) return;
    working.current = true;
    setLoading(true);
    setError(undefined);
    setReauthenticate(false);
    setAccount(undefined);
    try {
      const session = await ensureAuthenticated();
      const result = await apiRequest("/api/v1/users/me/deletion", {}, session.user.id);
      if (typeof result?.enabled !== "boolean" || ![null, "requested"].includes(result.status)) {
        throw new Error("Unable to check deletion status. Please try again.");
      }
      setAccount({ id: session.user.id, enabled: result.enabled, requested: result.status === "requested" });
    } catch (failure) {
      setReauthenticate(failure instanceof Error && "status" in failure && failure.status === 401);
      setError(failure instanceof Error ? failure.message : "Unable to check deletion status.");
    } finally { working.current = false; setLoading(false); }
  }
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []);

  async function submit() {
    if (working.current || !account?.enabled || account.requested) return;
    working.current = true;
    setBusy(true);
    setError(undefined);
    try {
      await submitAccountDeletion(confirmation, account.id, apiRequest);
      setAccount({ ...account, requested: true });
      setConfirmation("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to confirm deletion. Check its status and retry.");
    } finally { working.current = false; setBusy(false); }
  }

  async function signOut() {
    if (working.current) return;
    working.current = true;
    setBusy(true);
    setError(undefined);
    try {
      // The accepted deletion request already deactivated all devices server-side.
      const { error: failure } = await supabase.auth.signOut({ scope: "local" });
      if (failure) throw failure;
      router.replace("/sign-in");
    } catch {
      setError("Unable to sign out. Please try again; an accepted deletion request remains queued.");
    } finally { working.current = false; setBusy(false); }
  }

  return <Screen keyboard>
    <CircleButton label="နောက်သို့" disabled={busy || loading} onPress={() => router.replace('/')}>‹</CircleButton>
    <Type variant="title">{account?.requested ? 'ဖျက်သိမ်းရန် တောင်းဆိုပြီးပါပြီ' : 'အကောင့် ဖျက်သိမ်းခြင်း'}</Type>
    {loading ? <Loading /> : null}<Notice message={error} />
    {account?.requested ? <Panel>
      <Type>သင့်တောင်းဆိုမှုကို သိမ်းဆည်းပြီးပါပြီ။ အကောင့်အသုံးပြုမှု ရပ်တန့်ထားပြီး သင်ထွက်ပြီးနောက်လည်း ဖျက်သိမ်းမှု ဆက်လက်လုပ်ဆောင်ပါမည်။</Type>
      <Type variant="muted">ဤစာမျက်နှာသည် တောင်းဆိုမှုရရှိကြောင်း အတည်ပြုခြင်းသာ ဖြစ်ပါသည်။ ဖျက်သိမ်းမှု ပြီးဆုံးကြောင်း မဟုတ်ပါ။</Type>
      <Button title="အကောင့်မှ ထွက်မယ်" busy={busy} onPress={signOut} />
    </Panel> : <>
      {account?.enabled ? <Panel>
        <Type>အကောင့်၊ ရွေးချယ်မှုများ၊ အနှစ်ချုပ်များနှင့် သိမ်းထားသော အသံများကို အပြီးဖျက်သိမ်းပါမည်။ ပြန်ပြင်၍ မရပါ။</Type>
        <Field label="အတည်ပြုရန် DELETE ဟု ရိုက်ပါ" value={confirmation} onChangeText={setConfirmation} autoCapitalize="characters" autoCorrect={false} editable={!busy} />
        <Button title="အပြီးဖျက်သိမ်းရန် တောင်းဆိုမယ်" disabled={confirmation !== 'DELETE'} busy={busy} onPress={submit} />
      </Panel> : account ? <Panel><Type>အကောင့်ဖျက်သိမ်းမှုကို ယခု အသုံးမပြုနိုင်သေးပါ။ နောက်မှ ပြန်ကြိုးစားပါ။</Type></Panel> : null}
      {!loading ? <Button secondary disabled={busy} title="အခြေအနေ ပြန်စစ်မယ်" onPress={load} /> : null}
      {reauthenticate ? <Button secondary disabled={busy} title="ဝင်ရောက်ရန် ပြန်သွားမယ်" onPress={signOut} /> : null}
    </>}
  </Screen>;
}
