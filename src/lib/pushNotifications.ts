import { clearOfflineAudio } from '../services/offlineAudioStorage';
import { Platform } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { supabase } from "./supabase";
import { createPushLifecycle } from "./pushLifecycle";
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
      name: "နေ့သစ် — Nay Thit",
      description: "Notifications when your daily briefing is ready.",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      enableVibrate: true,
    },
  );
}

async function registerDevice(): Promise<string | null> {
  if (process.env.EXPO_PUBLIC_PUSH_ENABLED === "false") return null;
  if (Platform.OS !== "android") {
    console.log("Push registration currently supports Android only.");
    return null;
  }

  try {
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error || !session || session.user.is_anonymous) return null;
    const key = tokenStorageKey(session.user.id);
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

    // Persist before POST: a timeout can happen after registration succeeds.
    // Keep every attempted token until cleanup, including token rotations.
    const previous: string[] = JSON.parse(await AsyncStorage.getItem(key) ?? "[]");
    await AsyncStorage.setItem(key, JSON.stringify([...new Set([...previous, token])]));

    // Register the device token with the authenticated backend user.
    await apiRequest("/api/v1/push/register", {
      method: "POST",
      body: JSON.stringify({
        token,
        platform: "android",
      }),
    }, session.user.id);

    console.log("FCM device registered successfully.");

    return token;
  } catch (error) {
    console.warn("Push notification registration failed. Retry when connected.");
    throw error;
  }
}

function tokenStorageKey(userId: string) {
  return `push-tokens:${process.env.EXPO_PUBLIC_SUPABASE_URL}:${userId}`;
}

async function unregisterDevice(): Promise<void> {
  if (Platform.OS !== "android") return;
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error) throw new Error("Unable to check your session. Please try again.");
  if (!session || session.user.is_anonymous) return;
  const key = tokenStorageKey(session.user.id);
  const tokens: string[] = JSON.parse(await AsyncStorage.getItem(key) ?? "[]");
  // Also clean up registrations from versions that did not store tokens locally.
  if (tokens.length === 0 && process.env.EXPO_PUBLIC_PUSH_ENABLED !== "false" && (await Notifications.getPermissionsAsync()).granted) {
    const response = await Notifications.getDevicePushTokenAsync();
    const token = String(response.data ?? "").trim();
    if (token && token !== "undefined" && token !== "null") tokens.push(token);
  }
  for (const token of tokens) {
    await apiRequest("/api/v1/push/unregister", {
      method: "DELETE",
      body: JSON.stringify({ token, platform: "android" }),
    }, session.user.id);
  }
  await AsyncStorage.removeItem(key);
}

const lifecycle = createPushLifecycle(registerDevice, unregisterDevice, async () => {
  await clearOfflineAudio();
  const { error } = await supabase.auth.signOut({ scope: "local" });
  if (error) throw new Error("Unable to sign out. Please try again.");
});

export const registerForPushNotifications = lifecycle.register;
export const signOutWithPushCleanup = lifecycle.signOut;
