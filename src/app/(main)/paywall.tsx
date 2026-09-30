import { StyleSheet, Text, View } from "react-native";

export default function PaywallScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Subscription</Text>
      <Text style={styles.subtitle}>
        Premium features will be available here.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: "800",
  },
  subtitle: {
    marginTop: 10,
    fontSize: 16,
    textAlign: "center",
  },
});
