import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ensureAuthenticated } from "../lib/auth";

export default function Index() {
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    try {
      setLoading(true);

      const session = await ensureAuthenticated();

      console.log("CURRENT USER ID:", session?.user?.id);

      router.push("/phone-login");
    } catch (error) {
      console.error("START ERROR:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <Text style={styles.brand}>MORNING BRIEF</Text>

        <View>
          <Text style={styles.title}>
            မနက်တိုင်း{"\n"}
            သတင်းတွေကို{"\n"}
            လွယ်လွယ်ကူကူ သိပါစေ။
          </Text>

          <Text style={styles.subtitle}>
            သင်စိတ်ဝင်စားတဲ့ သတင်းတွေကို ရွေးချယ်ပြီး မနက်တိုင်း
            နားထောင်နိုင်ပါတယ်။
          </Text>
        </View>

        <Pressable
          style={styles.button}
          onPress={handleStart}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.buttonText}>စတင်မယ်</Text>
          )}
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },

  content: {
    flex: 1,
    paddingHorizontal: 24,
    paddingVertical: 32,
    justifyContent: "space-between",
  },

  brand: {
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 2,
    color: "#B11226",
  },

  title: {
    fontSize: 32,
    lineHeight: 44,
    fontWeight: "800",
    color: "#111111",
  },

  subtitle: {
    marginTop: 20,
    fontSize: 16,
    lineHeight: 26,
    color: "#ac0303",
  },

  button: {
    height: 56,
    borderRadius: 14,
    backgroundColor: "#B11226",
    alignItems: "center",
    justifyContent: "center",
  },

  buttonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "800",
  },
});
