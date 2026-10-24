import { useEffect } from "react";
import { Stack, router, usePathname } from "expo-router";
import * as Notifications from "expo-notifications";

import { registerForPushNotifications } from "../lib/pushNotifications";

export default function RootLayout() {
  const pathname = usePathname();

  // Register the device when the user enters the main app.
  useEffect(() => {
    const isMainScreen = pathname === "/home" || pathname === "/settings";

    if (!isMainScreen) {
      return;
    }

    let cancelled = false;

    async function registerDevice() {
      try {
        console.log("[FCM] Registration trigger reached.");

        const token = await registerForPushNotifications();

        if (cancelled) {
          return;
        }

        console.log(
          "[FCM] Registration finished.",
          token ? "Token returned." : "No token returned.",
        );
      } catch (error) {
        if (!cancelled) {
          console.error("[FCM] Registration failed:", error);
        }
      }
    }

    void registerDevice();

    return () => {
      cancelled = true;
    };
  }, [pathname]);

  // Handle notifications received while the app is open.
  useEffect(() => {
    const receivedSubscription = Notifications.addNotificationReceivedListener(
      (notification) => {
        console.log(
          "Notification received:",
          notification.request.content.data,
        );
      },
    );

    // Handle notification taps.
    const responseSubscription =
      Notifications.addNotificationResponseReceivedListener((response) => {
        const data = response.notification.request.content.data;

        console.log("Notification opened:", data);

        if (data?.type === "briefing_ready") {
          router.push("/home");
        }
      });

    return () => {
      receivedSubscription.remove();
      responseSubscription.remove();
    };
  }, []);

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: "slide_from_right",
      }}
    />
  );
}
