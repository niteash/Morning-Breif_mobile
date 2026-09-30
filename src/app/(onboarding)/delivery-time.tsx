import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import DateTimePicker, {
  DateTimePickerEvent,
} from "@react-native-community/datetimepicker";
import { router, useLocalSearchParams } from "expo-router";

import {
  updateMyPreferences,
  updateMyCategories,
} from "../../services/userApi";

export default function DeliveryTimeScreen() {
  const { categories } = useLocalSearchParams<{
    categories?: string;
  }>();

  console.log("DELIVERY TIME SCREEN MOUNTED");
  console.log("DELIVERY TIME CATEGORY PARAM:", categories);

  const [selectedTime, setSelectedTime] = useState(() => {
    const date = new Date();

    date.setHours(6);
    date.setMinutes(0);
    date.setSeconds(0);
    date.setMilliseconds(0);

    return date;
  });

  const [showPicker, setShowPicker] = useState(false);
  const [saving, setSaving] = useState(false);

  const timezone = "Asia/Yangon";

  const categoryIds =
    typeof categories === "string" ? categories.split(",").filter(Boolean) : [];

  function handleTimeChange(event: DateTimePickerEvent, selectedDate?: Date) {
    if (event.type === "dismissed") {
      setShowPicker(false);
      return;
    }

    setShowPicker(false);

    if (selectedDate) {
      setSelectedTime(selectedDate);
    }
  }

  function formatTime() {
    return selectedTime.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  }

  async function handleContinue() {
    if (saving) return;

    try {
      setSaving(true);

      if (categoryIds.length === 0) {
        throw new Error("No categories were selected.");
      }

      const deliveryHour = selectedTime.getHours();
      const deliveryMinute = selectedTime.getMinutes();

      console.log("CATEGORY PARAM:", categories);
      console.log("CATEGORY IDS:", categoryIds);

      console.log("DELIVERY TIME:", {
        hours: deliveryHour,
        minutes: deliveryMinute,
        timezone,
      });

      // Save delivery time
      const preferencesResponse = await updateMyPreferences({
        timezone,
        delivery_hour: deliveryHour,
        delivery_minute: deliveryMinute,
      });

      console.log("PREFERENCES SAVED THROUGH BACKEND:", preferencesResponse);

      // Save selected categories
      const categoriesResponse = await updateMyCategories(categoryIds);

      console.log("CATEGORIES SAVED THROUGH BACKEND:", categoriesResponse);

      console.log("ONBOARDING COMPLETED");

      // Go to Home
      router.replace("/home");
    } catch (error) {
      console.error("ONBOARDING SAVE ERROR:", error);
    } finally {
      setSaving(false);
    }
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <Text style={styles.title}>
          ဘယ်အချိန်မှာ{"\n"}
          Morning Brief ရချင်လဲ?
        </Text>

        <Text style={styles.description}>
          မနက်တိုင်း သင်ရွေးချယ်ထားတဲ့ သတင်းတွေကို ဒီအချိန်မှာ ရရှိပါမယ်။
        </Text>

        <Pressable
          style={styles.timeCard}
          onPress={() => setShowPicker(true)}
          disabled={saving}
        >
          <Text style={styles.timeLabel}>Delivery Time</Text>

          <Text style={styles.timeText}>{formatTime()}</Text>

          <Text style={styles.timezoneText}>Myanmar Time · {timezone}</Text>
        </Pressable>

        {showPicker && (
          <DateTimePicker
            value={selectedTime}
            mode="time"
            display="spinner"
            onChange={handleTimeChange}
          />
        )}

        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>Daily Morning Brief</Text>

          <Text style={styles.infoText}>
            သင်ရွေးချယ်ထားတဲ့ topics တွေကို တစ်စုတစ်စည်းတည်း brief တစ်ခုအဖြစ်
            ရရှိပါမယ်။
          </Text>
        </View>

        <View style={styles.selectedContainer}>
          <Text style={styles.selectedTitle}>Selected Topics</Text>

          <Text style={styles.selectedText}>
            {categoryIds.length} topics selected
          </Text>
        </View>

        <View style={styles.bottom}>
          <Pressable
            style={[styles.continueButton, saving && styles.disabledButton]}
            onPress={handleContinue}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.continueText}>Continue</Text>
            )}
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F7F7F7",
  },

  content: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 24,
  },

  title: {
    fontSize: 30,
    lineHeight: 40,
    fontWeight: "700",
    color: "#111111",
  },

  description: {
    marginTop: 14,
    fontSize: 15,
    lineHeight: 24,
    color: "#666666",
  },

  timeCard: {
    marginTop: 32,
    padding: 24,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E5E5E5",
  },

  timeLabel: {
    fontSize: 14,
    color: "#777777",
  },

  timeText: {
    marginTop: 8,
    fontSize: 40,
    fontWeight: "700",
    color: "#111111",
  },

  timezoneText: {
    marginTop: 6,
    fontSize: 13,
    color: "#999999",
  },

  infoCard: {
    marginTop: 18,
    padding: 20,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
  },

  infoTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#111111",
  },

  infoText: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 22,
    color: "#666666",
  },

  selectedContainer: {
    marginTop: 18,
    paddingHorizontal: 4,
  },

  selectedTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#111111",
  },

  selectedText: {
    marginTop: 4,
    fontSize: 13,
    color: "#777777",
  },

  bottom: {
    marginTop: "auto",
  },

  continueButton: {
    height: 56,
    borderRadius: 16,
    backgroundColor: "#111111",
    alignItems: "center",
    justifyContent: "center",
  },

  disabledButton: {
    opacity: 0.5,
  },

  continueText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "600",
  },
});
