import { router } from "expo-router";
import { View } from "react-native";

import {
  Brand,
  Button,
  Panel,
  Screen,
  Type,
} from "../components/ui/primitives";

export default function LinkEmailScreen() {
  return (
    <Screen>
      <Brand />

      <View style={{ paddingTop: 24, gap: 12 }}>
        <Type variant="hero">အီးမေးလ် အတည်ပြုခြင်း</Type>

        <Panel>
          <Type variant="muted">
            အီးမေးလ်အတည်ပြုလင့်ခ်ကို လုပ်ဆောင်ပြီးပါပြီ။ အကောင့်ဆက်တင်တွင်
            သင့်အီးမေးလ်အခြေအနေကို ပြန်လည်စစ်ဆေးနိုင်ပါသည်။
          </Type>
        </Panel>

        <Button
          title="ပင်မစာမျက်နှာသို့"
          onPress={() => router.replace("/home")}
        />
      </View>
    </Screen>
  );
}
