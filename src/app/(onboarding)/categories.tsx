import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";

import { getCategories } from "../../services/categoryApi";

type Category = {
  id: string;
  slug: string;
  name_en: string;
  name_my: string;
  active: boolean;
};

export default function CategoriesScreen() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [navigating, setNavigating] = useState(false);

  useEffect(() => {
    loadCategories();
  }, []);

  async function loadCategories() {
    try {
      console.log("LOADING CATEGORIES FROM BACKEND...");

      const response = await getCategories();

      console.log("BACKEND CATEGORIES:", response.categories);

      setCategories(response.categories);
    } catch (error) {
      console.error("CATEGORY API ERROR:", error);
    } finally {
      setLoading(false);
    }
  }

  function toggleCategory(categoryId: string) {
    if (navigating) return;

    setSelectedCategories((current) => {
      if (current.includes(categoryId)) {
        return current.filter((id) => id !== categoryId);
      }

      return [...current, categoryId];
    });
  }

  function handleContinue() {
    if (navigating) {
      return;
    }

    if (selectedCategories.length === 0) {
      console.log("NO CATEGORY SELECTED");
      return;
    }

    console.log("SELECTED CATEGORY IDS:", selectedCategories);

    setNavigating(true);

    const categoryParam = selectedCategories.join(",");

    console.log("NAVIGATING TO DELIVERY TIME:", categoryParam);

    router.push({
      pathname: "/delivery-time",
      params: {
        categories: categoryParam,
      },
    });
  }

  if (loading) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <ActivityIndicator size="large" />

        <Text style={styles.loadingText}>Categories ကို ပြင်ဆင်နေပါတယ်...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>ဘာတွေကို{"\n"}သိချင်လဲ?</Text>

        <Text style={styles.description}>
          သင်စိတ်ဝင်စားတဲ့ သတင်းအမျိုးအစားတွေကို ရွေးချယ်ပါ။
        </Text>

        <View style={styles.categoryList}>
          {categories.map((category) => {
            const selected = selectedCategories.includes(category.id);

            return (
              <Pressable
                key={category.id}
                onPress={() => toggleCategory(category.id)}
                disabled={navigating}
                style={[styles.categoryCard, selected && styles.selectedCard]}
              >
                <View style={styles.categoryTextContainer}>
                  <Text style={styles.categoryMyanmar}>{category.name_my}</Text>

                  <Text style={styles.categoryEnglish}>{category.name_en}</Text>
                </View>

                <View
                  style={[styles.checkbox, selected && styles.selectedCheckbox]}
                >
                  {selected && <Text style={styles.checkmark}>✓</Text>}
                </View>
              </Pressable>
            );
          })}
        </View>

        <Pressable
          style={[
            styles.continueButton,
            selectedCategories.length === 0 && styles.disabledButton,
            navigating && styles.disabledButton,
          ]}
          disabled={selectedCategories.length === 0 || navigating}
          onPress={handleContinue}
        >
          {navigating ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.continueText}>Continue</Text>
          )}
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F7F7F7",
  },

  content: {
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 40,
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

  categoryList: {
    marginTop: 30,
    gap: 12,
  },

  categoryCard: {
    minHeight: 76,
    paddingHorizontal: 18,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E5E5E5",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  selectedCard: {
    borderColor: "#111111",
    borderWidth: 2,
  },

  categoryTextContainer: {
    flex: 1,
  },

  categoryMyanmar: {
    fontSize: 17,
    fontWeight: "600",
    color: "#111111",
  },

  categoryEnglish: {
    marginTop: 4,
    fontSize: 13,
    color: "#888888",
  },

  checkbox: {
    width: 26,
    height: 26,
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: "#CCCCCC",
    alignItems: "center",
    justifyContent: "center",
  },

  selectedCheckbox: {
    backgroundColor: "#111111",
    borderColor: "#111111",
  },

  checkmark: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "700",
  },

  continueButton: {
    height: 56,
    marginTop: 32,
    borderRadius: 16,
    backgroundColor: "#111111",
    alignItems: "center",
    justifyContent: "center",
  },

  disabledButton: {
    opacity: 0.4,
  },

  continueText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "600",
  },

  loadingContainer: {
    flex: 1,
    backgroundColor: "#F7F7F7",
    alignItems: "center",
    justifyContent: "center",
  },

  loadingText: {
    marginTop: 14,
    color: "#666666",
    fontSize: 14,
  },
});
