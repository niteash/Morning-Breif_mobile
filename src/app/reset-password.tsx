import { router } from "expo-router";
import { useState } from "react";
import { View } from "react-native";

import { supabase } from "../lib/supabase";
import { saveAccountPassword } from "../lib/emailAuth";
import { useAuthFlow } from "../features/auth/AuthFlowProvider";

import {
  Brand,
  Button,
  Field,
  Notice,
  Panel,
  Screen,
  Type,
} from "../components/ui/primitives";

export default function ResetPasswordScreen() {
  const { recoveryUser, finishRecovery } = useAuthFlow();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleReset() {
    if (busy || !recoveryUser) return;

    setBusy(true);
    setError(null);

    try {
      if (password !== confirmPassword) {
        throw new Error("စကားဝှက်နှစ်ခု မတူညီပါ။");
      }

      await saveAccountPassword(supabase, recoveryUser, password);

      await finishRecovery();
      router.replace("/home");
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "စကားဝှက် ပြောင်းလဲ၍ မရပါ။",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen keyboard>
      <Brand />

      <View style={{ paddingTop: 24, gap: 12 }}>
        <Type variant="hero">စကားဝှက်အသစ် သတ်မှတ်မယ်</Type>

        <Type variant="muted">သင့်အကောင့်အတွက် စကားဝှက်အသစ် ထည့်ပါ။</Type>
      </View>

      {!recoveryUser ? (
        <Panel>
          <Type variant="muted">
            စကားဝှက်ပြန်လည်သတ်မှတ်ရန် အတည်ပြုထားသော လင့်ခ်တစ်ခု လိုအပ်ပါသည်။
          </Type>
          <Button
            secondary
            title="အကောင့်ဝင်ရန်"
            onPress={() => router.replace("/sign-in")}
          />
        </Panel>
      ) : (
        <>
          <Panel>
            <View style={{ gap: 16 }}>
              <Field
                label="စကားဝှက်အသစ်"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                autoCapitalize="none"
                editable={!busy}
                placeholder="အနည်းဆုံး ၁၂ လုံး"
              />

              <Field
                label="စကားဝှက် အတည်ပြုရန်"
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                secureTextEntry
                autoCapitalize="none"
                editable={!busy}
                placeholder="စကားဝှက် ထပ်ထည့်ပါ"
              />
            </View>
          </Panel>

          <Notice message={error} />

          <Button
            title={busy ? "သိမ်းဆည်းနေပါသည်…" : "စကားဝှက် ပြောင်းမယ်"}
            busy={busy}
            disabled={
              busy || password.length < 12 || confirmPassword.length === 0
            }
            onPress={handleReset}
          />
        </>
      )}
    </Screen>
  );
}
