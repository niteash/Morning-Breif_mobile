import { Platform } from "react-native";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";

import { apiRequest } from "./api";

const ANDROID_NOTIFICATION_CHANNEL_ID = "morning-brief";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

async function configureAndroidNotificationChannel(): Promise<void> {
  if (Platform.OS !== "android") {
    return;
  }

  await Notifications.setNotificationChannelAsync(
    ANDROID_NOTIFICATION_CHANNEL_ID,
    {
      name: "Morning Brief",
      description: "Notifications when your daily briefing is ready.",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      enableVibrate: true,
    },
  );
}

export async function registerForPushNotifications(): Promise<string | null> {
  if (Platform.OS !== "android") {
    console.log("Push registration currently supports Android only.");
    return null;
  }

  if (!Device.isDevice) {
    console.warn(
      "[FCM] Running in an emulator. Attempting native FCM registration.",
    );
  }

  try {
    await configureAndroidNotificationChannel();

    let permission = await Notifications.getPermissionsAsync();

    if (!permission.granted) {
      permission = await Notifications.requestPermissionsAsync();
    }

    if (!permission.granted) {
      console.warn("Notification permission was not granted.");
      return null;
    }

    // Get the native Firebase Cloud Messaging token.
    const tokenResponse = await Notifications.getDevicePushTokenAsync();
    const token = String(tokenResponse.data ?? "").trim();

    if (!token || token === "undefined" || token === "null") {
      throw new Error("Firebase did not return a valid device push token.");
    }

    // Register the device token with the authenticated backend user.
    await apiRequest("/api/v1/push/register", {
      method: "POST",
      body: JSON.stringify({
        token,
        platform: "android",
      }),
    });

    console.log("FCM device registered successfully.");

    return token;
  } catch (error) {
    console.error("Push notification registration failed:", error);
    throw error;
  }
}

export async function unregisterPushNotifications(): Promise<void> {
  if (Platform.OS !== "android" || !Device.isDevice) {
    return;
  }

  try {
    const tokenResponse = await Notifications.getDevicePushTokenAsync();
    const token = String(tokenResponse.data ?? "").trim();

    if (!token || token === "undefined" || token === "null") {
      return;
    }

    await apiRequest("/api/v1/push/unregister", {
      method: "DELETE",
      body: JSON.stringify({
        token,
        platform: "android",
      }),
    });

    console.log("FCM device unregistered successfully.");
  } catch (error) {
    console.error("Push notification unregistration failed:", error);
    throw error;
  }
}
