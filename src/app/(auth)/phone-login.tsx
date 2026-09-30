import { router } from "expo-router";
import {
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useState } from "react";

export default function PhoneLoginScreen() {
  const [phone, setPhone] = useState("");

  const handleContinue = () => {
    if (!phone.trim()) return;

    router.push({
      pathname: "/otp-verify",
      params: {
        phone,
      },
    });
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.back}>‹ Back</Text>
        </Pressable>

        <View style={styles.header}>
          <Text style={styles.title}>ဖုန်းနံပါတ်ထည့်ပါ</Text>

          <Text style={styles.description}>
            သင့်အကောင့်ကို ဖန်တီးရန် သို့မဟုတ် ဝင်ရောက်ရန် ဖုန်းနံပါတ်ကို
            အသုံးပြုပါ။
          </Text>
        </View>

        <View style={styles.inputContainer}>
          <View style={styles.country}>
            <Text style={styles.countryText}>🇲🇲 +95</Text>
          </View>

          <TextInput
            value={phone}
            onChangeText={setPhone}
            placeholder="9xxxxxxxxx"
            placeholderTextColor="#999999"
            keyboardType="phone-pad"
            style={styles.input}
            maxLength={12}
          />
        </View>
      </View>

      <View style={styles.bottom}>
        <Pressable
          style={[styles.button, !phone.trim() && styles.buttonDisabled]}
          disabled={!phone.trim()}
          onPress={handleContinue}
        >
          <Text style={styles.buttonText}>ဆက်လုပ်မယ်</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FAFAFA",
  },

  content: {
    flex: 1,
    padding: 24,
  },

  back: {
    fontSize: 16,
    color: "#B11226",
    fontWeight: "600",
  },

  header: {
    marginTop: 60,
  },

  title: {
    fontSize: 28,
    fontWeight: "800",
    color: "#161616",
  },

  description: {
    fontSize: 15,
    lineHeight: 24,
    color: "#777777",
    marginTop: 12,
  },

  inputContainer: {
    flexDirection: "row",
    marginTop: 32,
    gap: 10,
  },

  country: {
    height: 56,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: "#DDDDDD",
    borderRadius: 14,
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
  },

  countryText: {
    fontSize: 15,
    color: "#333333",
  },

  input: {
    flex: 1,
    height: 56,
    borderWidth: 1,
    borderColor: "#DDDDDD",
    borderRadius: 14,
    paddingHorizontal: 16,
    fontSize: 16,
    color: "#161616",
    backgroundColor: "#FFFFFF",
  },

  bottom: {
    padding: 24,
  },

  button: {
    height: 56,
    borderRadius: 16,
    backgroundColor: "#B11226",
    alignItems: "center",
    justifyContent: "center",
  },

  buttonDisabled: {
    opacity: 0.4,
  },

  buttonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "700",
  },
});
