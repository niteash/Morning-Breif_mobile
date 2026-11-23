import { Stack } from "expo-router";
import { AuthGate } from "../../components/AuthGate";

export default function OnboardingLayout() {
  return <AuthGate><Stack screenOptions={{ headerShown: false }} /></AuthGate>;
}
