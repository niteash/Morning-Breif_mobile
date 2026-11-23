import { router } from "expo-router";
import {
  Button,
  Loading,
  Notice,
  Screen,
  Type,
} from "../../components/ui/primitives";
import { useAuthFlow } from "../../features/auth/AuthFlowProvider";

export default function AuthCallbackScreen() {
  const { initializing, processing, error } = useAuthFlow();

  return (
    <Screen>
      <Type variant="hero">အီးမေးလ် အတည်ပြုခြင်း</Type>

      {initializing || processing ? (
        <>
          <Loading />
          <Type variant="muted">အကောင့်လင့်ခ်ကို စစ်ဆေးနေပါသည်။</Type>
        </>
      ) : (
        <>
          <Notice
            message={
              error ??
              "အကောင့်အတည်ပြုမှု မပြီးဆုံးသေးပါ။ လင့်ခ်ကို ပြန်လည်စစ်ဆေးပါ။"
            }
          />

          <Button
            title="အကောင့်ဝင်ရန်"
            onPress={() => router.replace("/sign-in")}
          />
        </>
      )}
    </Screen>
  );
}
