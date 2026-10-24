import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { testBriefingAPI } from "@/lib/checkSession";

export default function SettingsScreen() {
  const [isTesting, setIsTesting] = useState(false);

  const handleTestAPI = async () => {
    if (isTesting) return;

    setIsTesting(true);

    try {
      await testBriefingAPI();
    } catch (error) {
      console.error("Briefing API test failed:", error);
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Settings</Text>

      <Text style={styles.subtitle}>
        Manage your preferences and test your Morning Brief connection.
      </Text>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Test Briefing API"
        disabled={isTesting}
        onPress={handleTestAPI}
        style={({ pressed }) => [
          styles.testButton,
          pressed && styles.buttonPressed,
          isTesting && styles.buttonDisabled,
        ]}
      >
        {isTesting ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.buttonText}>Test Briefing API</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#FFFFFF",
  },
  title: {
    fontSize: 28,
    fontWeight: "800",
    color: "#111111",
  },
  subtitle: {
    marginTop: 10,
    fontSize: 16,
    lineHeight: 24,
    textAlign: "center",
    color: "#666666",
  },
  testButton: {
    backgroundColor: "#DC2626",
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    minWidth: 200,
    minHeight: 50,
    marginTop: 24,
  },
  buttonPressed: {
    opacity: 0.8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "600",
  },
});
