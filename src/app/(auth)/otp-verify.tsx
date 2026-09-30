import { router, useLocalSearchParams } from "expo-router";
import {
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useState } from "react";

export default function OTPVerifyScreen() {
  const { phone } = useLocalSearchParams<{ phone?: string }>();
  const [otp, setOtp] = useState("");

  const handleVerify = () => {
    if (otp.length !== 6) return;

    router.replace("/categories");
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.back}>‹ Back</Text>
        </Pressable>

        <View style={styles.header}>
          <Text style={styles.title}>OTP ထည့်ပါ</Text>

          <Text style={styles.description}>
            {phone ? `+95 ${phone}` : "သင့်ဖုန်းနံပါတ်"} သို့ verification code
            ပို့ပေးပါမယ်။
          </Text>
        </View>

        <TextInput
          value={otp}
          onChangeText={setOtp}
          placeholder="000000"
          placeholderTextColor="#AAAAAA"
          keyboardType="number-pad"
          maxLength={6}
          style={styles.otpInput}
        />
      </View>

      <View style={styles.bottom}>
        <Pressable
          style={[styles.button, otp.length !== 6 && styles.buttonDisabled]}
          disabled={otp.length !== 6}
          onPress={handleVerify}
        >
          <Text style={styles.buttonText}>အတည်ပြုမယ်</Text>
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
    marginTop: 12,
    fontSize: 15,
    lineHeight: 24,
    color: "#777777",
  },

  otpInput: {
    marginTop: 32,
    height: 60,
    borderWidth: 1,
    borderColor: "#DDDDDD",
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    textAlign: "center",
    letterSpacing: 10,
    fontSize: 24,
    fontWeight: "700",
    color: "#161616",
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
