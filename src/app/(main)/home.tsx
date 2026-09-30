import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Linking,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useAudioPlayer, useAudioPlayerStatus } from "expo-audio";

import { SafeAreaView } from "react-native-safe-area-context";

import {
  generateBriefing,
  GeneratedBriefing,
  getSavedTodayBriefing,
  getTodayBriefing,
  SavedBriefing,
  TodayBriefing,
} from "../../services/briefingApi";

import { getNews, NewsItem } from "../../services/newsApi";

export default function HomeScreen() {
  /* ===================================================== */
  /* STATE */
  /* ===================================================== */

  const [news, setNews] = useState<NewsItem[]>([]);

  const [briefing, setBriefing] = useState<TodayBriefing | null>(null);

  const [generatedBriefing, setGeneratedBriefing] =
    useState<GeneratedBriefing | null>(null);

  const [savedBriefing, setSavedBriefing] = useState<SavedBriefing | null>(
    null,
  );

  const [loading, setLoading] = useState(true);

  const [briefingLoading, setBriefingLoading] = useState(true);

  const [generatingBriefing, setGeneratingBriefing] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [briefingError, setBriefingError] = useState<string | null>(null);

  const [generationError, setGenerationError] = useState<string | null>(null);

  /* ===================================================== */
  /* AUDIO */
  /* ===================================================== */

  const audioUrl = savedBriefing?.audio_url ?? null;

  const player = useAudioPlayer(audioUrl || null);

  const playerStatus = useAudioPlayerStatus(player);

  const isPlaying = playerStatus.playing;

  /* ===================================================== */
  /* LOAD NEWS */
  /* ===================================================== */

  async function loadNews() {
    try {
      setLoading(true);
      setError(null);

      console.log("LOADING NEWS FROM BACKEND...");

      const response = await getNews({
        limit: 20,
      });

      console.log("NEWS RESPONSE:", response);

      setNews(Array.isArray(response.news) ? response.news : []);
    } catch (err) {
      console.error("NEWS LOAD ERROR:", err);

      setError(err instanceof Error ? err.message : "Failed to load news");
    } finally {
      setLoading(false);
    }
  }

  /* ===================================================== */
  /* LOAD TODAY'S STORY BRIEFING */
  /* ===================================================== */

  async function loadBriefing() {
    try {
      setBriefingLoading(true);
      setBriefingError(null);

      console.log("LOADING TODAY'S STORY BRIEFING...");

      const data = await getTodayBriefing();

      console.log(
        "TODAY'S BRIEFING RAW RESPONSE:",
        JSON.stringify(data, null, 2),
      );

      if (!data || !Array.isArray(data.categories)) {
        throw new Error("Invalid briefing response: categories is missing");
      }

      setBriefing(data);
    } catch (err) {
      console.error("BRIEFING ERROR:", err);

      setBriefing(null);

      setBriefingError(
        err instanceof Error ? err.message : "Failed to load today's briefing",
      );
    } finally {
      setBriefingLoading(false);
    }
  }

  /* ===================================================== */
  /* LOAD SAVED AI BRIEFING */
  /* ===================================================== */

  async function loadSavedBriefing() {
    try {
      console.log("LOADING SAVED AI BRIEFING...");

      const response = await getSavedTodayBriefing();

      console.log("SAVED AI BRIEFING:", JSON.stringify(response, null, 2));

      setSavedBriefing(response.briefing ?? null);

      return response.briefing ?? null;
    } catch (err) {
      console.error("SAVED BRIEFING ERROR:", err);

      return null;
    }
  }

  /* ===================================================== */
  /* GENERATE AI BRIEFING */
  /* ===================================================== */

  async function handleGenerateBriefing() {
    try {
      setGeneratingBriefing(true);
      setGenerationError(null);

      console.log("================================");

      console.log("GENERATING AI MORNING BRIEFING...");

      const result = await generateBriefing();

      console.log("AI BRIEFING GENERATED:", JSON.stringify(result, null, 2));

      if (!result?.briefing?.script) {
        throw new Error("AI returned an empty briefing");
      }

      setGeneratedBriefing(result.briefing);

      /*
       * Important:
       *
       * The generate endpoint returns the
       * Storage path.
       *
       * We call /today/saved again so the
       * backend can return the signed URL.
       */

      await loadSavedBriefing();

      /*
       * Refresh story intelligence too,
       * because generation may have used
       * the latest stories.
       */

      await loadBriefing();
    } catch (err) {
      console.error("AI BRIEFING GENERATION ERROR:", err);

      setGenerationError(
        err instanceof Error ? err.message : "Failed to generate AI briefing",
      );
    } finally {
      setGeneratingBriefing(false);
    }
  }

  /* ===================================================== */
  /* AUDIO PLAY / PAUSE */
  /* ===================================================== */

  function togglePlayback() {
    if (!audioUrl) {
      console.log("NO SIGNED AUDIO URL AVAILABLE");

      return;
    }

    try {
      if (playerStatus.playing) {
        player.pause();
      } else {
        player.play();
      }
    } catch (error) {
      console.error("AUDIO PLAYBACK ERROR:", error);
    }
  }

  /* ===================================================== */
  /* OPEN ARTICLE */
  /* ===================================================== */

  async function openArticle(url: string) {
    try {
      const supported = await Linking.canOpenURL(url);

      if (!supported) {
        console.error("Cannot open URL:", url);

        return;
      }

      await Linking.openURL(url);
    } catch (error) {
      console.error("ARTICLE OPEN ERROR:", error);
    }
  }

  /* ===================================================== */
  /* REFRESH */
  /* ===================================================== */

  async function refreshAll() {
    await Promise.all([loadNews(), loadBriefing(), loadSavedBriefing()]);
  }

  /* ===================================================== */
  /* INITIAL LOAD */
  /* ===================================================== */

  useEffect(() => {
    loadNews();
    loadBriefing();
    loadSavedBriefing();
  }, []);

  /* ===================================================== */
  /* STATS */
  /* ===================================================== */

  const totalStories = useMemo(() => {
    if (!briefing || !Array.isArray(briefing.categories)) {
      return 0;
    }

    return briefing.categories.reduce(
      (total, category) =>
        total + (Array.isArray(category.stories) ? category.stories.length : 0),
      0,
    );
  }, [briefing]);

  const activeCategories = useMemo(() => {
    if (!briefing || !Array.isArray(briefing.categories)) {
      return 0;
    }

    return briefing.categories.filter(
      (category) =>
        Array.isArray(category.stories) && category.stories.length > 0,
    ).length;
  }, [briefing]);

  const briefingScript =
    generatedBriefing?.script || savedBriefing?.script || null;

  /* ===================================================== */
  /* INITIAL LOADING */
  /* ===================================================== */

  if (loading && briefingLoading) {
    return (
      <SafeAreaView style={styles.container} edges={["top", "left", "right"]}>
        <View style={styles.loadingScreen}>
          <View style={styles.loadingMark}>
            <Text style={styles.loadingMarkText}>M</Text>
          </View>

          <Text style={styles.loadingTitle}>Morning Brief</Text>

          <Text style={styles.loadingText}>
            သတင်းအချက်အလက်များကို စုစည်းနေပါတယ်...
          </Text>

          <ActivityIndicator
            size="small"
            color="#E31B23"
            style={styles.loader}
          />
        </View>
      </SafeAreaView>
    );
  }

  /* ===================================================== */
  /* COMPLETE FAILURE */
  /* ===================================================== */

  if (error && !briefing) {
    return (
      <SafeAreaView style={styles.container} edges={["top", "left", "right"]}>
        <View style={styles.errorScreen}>
          <View style={styles.errorIcon}>
            <Text style={styles.errorIconText}>!</Text>
          </View>

          <Text style={styles.errorTitle}>သတင်းရယူလို့ မရသေးပါ</Text>

          <Text style={styles.errorText}>{error}</Text>

          <Pressable style={styles.retryButton} onPress={refreshAll}>
            <Text style={styles.retryText}>Try Again</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  /* ===================================================== */
  /* MAIN SCREEN */
  /* ===================================================== */

  return (
    <SafeAreaView style={styles.container} edges={["top", "left", "right"]}>
      <FlatList
        data={news}
        keyExtractor={(item) => item.id}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.list}
        refreshing={loading || briefingLoading}
        onRefresh={refreshAll}
        /* ================================================= */
        /* HEADER */
        /* ================================================= */

        ListHeaderComponent={
          <View>
            {/* --------------------------------------------- */}
            {/* HEADER */}
            {/* --------------------------------------------- */}

            <View style={styles.topHeader}>
              <View style={styles.headerContent}>
                <View style={styles.statusRow}>
                  <View style={styles.liveDot} />

                  <Text style={styles.statusText}>MORNING BRIEF</Text>
                </View>

                <Text style={styles.greeting}>မင်္ဂလာနံနက်ခင်းပါ</Text>

                <Text style={styles.title}>Morning Brief</Text>

                <Text style={styles.subtitle}>
                  သင့်အတွက် အရေးကြီးဆုံးသတင်းများ
                </Text>
              </View>

              <View style={styles.appMark}>
                <Text style={styles.appMarkText}>M</Text>
              </View>
            </View>

            {/* --------------------------------------------- */}
            {/* AUDIO / AI BRIEF CARD */}
            {/* --------------------------------------------- */}

            {briefingScript ? (
              <View style={styles.audioCard}>
                <View style={styles.audioCardTop}>
                  <View style={styles.audioCardTitleBox}>
                    <Text style={styles.audioEyebrow}>TODAY'S BRIEF</Text>

                    <Text style={styles.audioCardTitle}>
                      နားဆင်ရန် အသင့်ဖြစ်ပါပြီ
                    </Text>
                  </View>

                  <View style={styles.readyBadge}>
                    <View style={styles.readyDot} />

                    <Text style={styles.readyBadgeText}>READY</Text>
                  </View>
                </View>

                {/* ----------------------------------------- */}
                {/* PLAYER */}
                {/* ----------------------------------------- */}

                <View style={styles.playerRow}>
                  <Pressable
                    onPress={togglePlayback}
                    disabled={!audioUrl}
                    style={({ pressed }) => [
                      styles.playButton,
                      !audioUrl && styles.playButtonDisabled,
                      pressed && audioUrl && styles.playButtonPressed,
                    ]}
                  >
                    <Text style={styles.playButtonText}>
                      {isPlaying ? "Ⅱ" : "▶"}
                    </Text>
                  </Pressable>

                  <View style={styles.playerInfo}>
                    <Text style={styles.playerTitle}>Morning Brief Audio</Text>

                    <Text style={styles.playerSubtitle}>
                      မြန်မာဘာသာ • AI Audio
                    </Text>
                  </View>

                  <View style={styles.audioStatus}>
                    <View style={styles.audioStatusDot} />

                    <Text style={styles.audioStatusText}>
                      {isPlaying ? "PLAYING" : "AUDIO"}
                    </Text>
                  </View>
                </View>

                {!audioUrl ? (
                  <Text style={styles.audioUnavailable}>
                    Audio ကို ပြင်ဆင်နေပါတယ်...
                  </Text>
                ) : null}

                {/* ----------------------------------------- */}
                {/* SCRIPT */}
                {/* ----------------------------------------- */}

                <View style={styles.scriptSection}>
                  <View style={styles.scriptSectionHeader}>
                    <Text style={styles.scriptEyebrow}>TRANSCRIPT</Text>

                    <Text style={styles.scriptLanguage}>BURMESE</Text>
                  </View>

                  <Text style={styles.scriptText}>{briefingScript}</Text>
                </View>

                {/* ----------------------------------------- */}
                {/* FOOTER */}
                {/* ----------------------------------------- */}

                <View style={styles.scriptFooter}>
                  <Text style={styles.scriptFooterText}>
                    Generated by Morning Brief AI
                  </Text>

                  <Text style={styles.scriptFooterStatus}>
                    {formatGeneratedTime(
                      generatedBriefing?.generated_at ||
                        savedBriefing?.updated_at ||
                        savedBriefing?.created_at ||
                        "",
                    )}
                  </Text>
                </View>
              </View>
            ) : null}

            {/* --------------------------------------------- */}
            {/* GENERATE CARD */}
            {/* --------------------------------------------- */}

            <View style={styles.generationCard}>
              <View style={styles.generationHeader}>
                <View style={styles.generationIcon}>
                  <Text style={styles.generationIconText}>✦</Text>
                </View>

                <View style={styles.generationHeaderText}>
                  <Text style={styles.generationEyebrow}>AI INTELLIGENCE</Text>

                  <Text style={styles.generationTitle}>
                    Create Today's Brief
                  </Text>
                </View>
              </View>

              <Text style={styles.generationDescription}>
                သင့်ရွေးချယ်ထားတဲ့ ကဏ္ဍတွေထဲက အရေးကြီးဆုံးသတင်းတွေကို AI က
                မြန်မာဘာသာဖြင့် အကျဉ်းချုပ်ပေးပါမယ်။
              </Text>

              <Pressable
                style={({ pressed }) => [
                  styles.generateButton,
                  generatingBriefing && styles.generateButtonDisabled,
                  pressed &&
                    !generatingBriefing &&
                    styles.generateButtonPressed,
                ]}
                onPress={handleGenerateBriefing}
                disabled={generatingBriefing}
              >
                {generatingBriefing ? (
                  <>
                    <ActivityIndicator size="small" color="#FFFFFF" />

                    <Text style={styles.generateButtonText}>Preparing...</Text>
                  </>
                ) : (
                  <Text style={styles.generateButtonText}>
                    {briefingScript
                      ? "Regenerate Today's Brief"
                      : "Generate Today's Brief"}
                  </Text>
                )}
              </Pressable>

              {generationError ? (
                <View style={styles.generationErrorBox}>
                  <Text style={styles.generationErrorTitle}>
                    Briefing generation failed
                  </Text>

                  <Text style={styles.generationError}>{generationError}</Text>
                </View>
              ) : null}
            </View>

            {/* --------------------------------------------- */}
            {/* INTELLIGENCE SUMMARY */}
            {/* --------------------------------------------- */}

            <View style={styles.intelligenceCard}>
              <View style={styles.intelligenceHeader}>
                <View style={styles.intelligenceIcon}>
                  <Text style={styles.intelligenceIconText}>✦</Text>
                </View>

                <View style={styles.intelligenceHeaderText}>
                  <Text style={styles.intelligenceLabel}>INTELLIGENCE</Text>

                  <Text style={styles.intelligenceTitle}>
                    Today's News Analysis
                  </Text>
                </View>

                <View style={styles.onlineBadge}>
                  <View style={styles.onlineDot} />

                  <Text style={styles.onlineText}>LIVE</Text>
                </View>
              </View>

              {briefingLoading ? (
                <View style={styles.briefingLoading}>
                  <ActivityIndicator size="small" color="#E31B23" />

                  <Text style={styles.briefingLoadingText}>
                    Analyzing today's news...
                  </Text>
                </View>
              ) : briefingError ? (
                <View style={styles.briefingErrorBox}>
                  <Text style={styles.briefingErrorTitle}>
                    Briefing unavailable
                  </Text>

                  <Text style={styles.briefingError}>{briefingError}</Text>

                  <Pressable
                    onPress={loadBriefing}
                    style={styles.smallRetryButton}
                  >
                    <Text style={styles.smallRetryText}>Retry</Text>
                  </Pressable>
                </View>
              ) : briefing ? (
                <View>
                  <Text style={styles.intelligenceDescription}>
                    AI က သင့်ရွေးချယ်ထားတဲ့ ကဏ္ဍများထဲမှ အရေးကြီးတဲ့ သတင်းတွေကို
                    စုစည်းထားပါတယ်။
                  </Text>

                  <View style={styles.statsRow}>
                    <View style={styles.statBox}>
                      <Text style={styles.statValue}>{activeCategories}</Text>

                      <Text style={styles.statLabel}>CATEGORIES</Text>
                    </View>

                    <View style={styles.statDivider} />

                    <View style={styles.statBox}>
                      <Text style={styles.statValue}>{totalStories}</Text>

                      <Text style={styles.statLabel}>STORIES</Text>
                    </View>

                    <View style={styles.statDivider} />

                    <View style={styles.statBox}>
                      <Text style={styles.statValue}>24h</Text>

                      <Text style={styles.statLabel}>WINDOW</Text>
                    </View>
                  </View>

                  <View style={styles.analyzedRow}>
                    <View style={styles.analyzedIcon}>
                      <Text style={styles.analyzedIconText}>✓</Text>
                    </View>

                    <Text style={styles.analyzedText}>
                      Updated {briefing.date}
                    </Text>
                  </View>
                </View>
              ) : (
                <Text style={styles.emptyText}>Today's briefing မရသေးပါ။</Text>
              )}
            </View>

            {/* --------------------------------------------- */}
            {/* CATEGORY INTELLIGENCE */}
            {/* --------------------------------------------- */}

            {briefing ? (
              <View style={styles.categoriesWrapper}>
                <View style={styles.sectionHeader}>
                  <View>
                    <Text style={styles.sectionEyebrow}>INTELLIGENCE FEED</Text>

                    <Text style={styles.sectionTitle}>Your News</Text>
                  </View>

                  <Text style={styles.sectionCount}>
                    {totalStories} stories
                  </Text>
                </View>

                {briefing.categories.map((category) => (
                  <View key={category.category.id} style={styles.categoryCard}>
                    <View style={styles.categoryHeader}>
                      <View style={styles.categoryIcon}>
                        <Text style={styles.categoryIconText}>
                          {getCategoryIcon(category.category.slug)}
                        </Text>
                      </View>

                      <View style={styles.categoryNameBox}>
                        <Text style={styles.categoryTitle}>
                          {category.category.name_my}
                        </Text>

                        <Text style={styles.categoryEnglish}>
                          {category.category.name_en.toUpperCase()}
                        </Text>
                      </View>

                      <View style={styles.storyCountBadge}>
                        <Text style={styles.storyCountText}>
                          {category.stories.length}
                        </Text>
                      </View>
                    </View>

                    {category.stories.length === 0 ? (
                      <View style={styles.emptyCategory}>
                        <Text style={styles.emptyText}>
                          ဒီကဏ္ဍအတွက် သတင်းမတွေ့သေးပါ။
                        </Text>
                      </View>
                    ) : (
                      category.stories.slice(0, 5).map((story, index) => (
                        <Pressable
                          key={story.id}
                          style={({ pressed }) => [
                            styles.storyCard,
                            pressed && styles.pressedCard,
                          ]}
                          onPress={() => openArticle(story.url)}
                        >
                          <View style={styles.storyNumber}>
                            <Text style={styles.storyNumberText}>
                              {String(index + 1).padStart(2, "0")}
                            </Text>
                          </View>

                          <View style={styles.storyContent}>
                            <Text style={styles.storyTitle} numberOfLines={3}>
                              {story.title}
                            </Text>

                            <View style={styles.storyMeta}>
                              <Text style={styles.storySource}>
                                {story.source}
                              </Text>

                              <Text style={styles.storyArrow}>→</Text>
                            </View>
                          </View>
                        </Pressable>
                      ))
                    )}
                  </View>
                ))}
              </View>
            ) : null}

            {/* --------------------------------------------- */}
            {/* LATEST NEWS */}
            {/* --------------------------------------------- */}

            <View style={styles.latestHeader}>
              <View>
                <Text style={styles.sectionEyebrow}>LIVE SOURCES</Text>

                <Text style={styles.latestTitle}>Latest News</Text>
              </View>

              <View style={styles.liveSourceBadge}>
                <View style={styles.liveDotSmall} />

                <Text style={styles.liveSourceText}>LIVE</Text>
              </View>
            </View>
          </View>
        }
        /* ================================================= */
        /* NEWS */
        /* ================================================= */

        renderItem={({ item }) => (
          <Pressable
            style={({ pressed }) => [
              styles.newsCard,
              pressed && styles.pressedCard,
            ]}
            onPress={() => openArticle(item.url)}
          >
            <View style={styles.newsTopRow}>
              <Text style={styles.source}>{item.source}</Text>

              <Text style={styles.openArrow}>↗</Text>
            </View>

            <Text style={styles.newsTitle}>{item.title}</Text>

            {item.description ? (
              <Text style={styles.description} numberOfLines={3}>
                {item.description}
              </Text>
            ) : null}

            {item.published_at ? (
              <Text style={styles.date}>{formatDate(item.published_at)}</Text>
            ) : null}
          </Pressable>
        )}
        /* ================================================= */
        /* EMPTY */
        /* ================================================= */

        ListEmptyComponent={
          <View style={styles.emptyNews}>
            <View style={styles.emptyNewsIcon}>
              <Text style={styles.emptyNewsIconText}>✦</Text>
            </View>

            <Text style={styles.emptyNewsTitle}>No news available</Text>

            <Text style={styles.emptyNewsText}>သတင်းများ မရရှိသေးပါ။</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

/* ========================================================= */
/* HELPERS */
/* ========================================================= */

function getCategoryIcon(slug: string) {
  switch (slug) {
    case "tech":
    case "technology":
      return "⌘";

    case "business":
      return "↗";

    case "football":
      return "⚽";

    case "world":
      return "◎";

    case "myanmar":
      return "✦";

    default:
      return "•";
  }
}

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

function formatGeneratedTime(value: string) {
  try {
    return new Date(value).toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "READY";
  }
}

/* ========================================================= */
/* STYLES */
/* ========================================================= */

const styles = StyleSheet.create({
  /* ===================================================== */
  /* BASE */
  /* ===================================================== */

  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },

  list: {
    paddingBottom: 50,
  },

  /* ===================================================== */
  /* LOADING */
  /* ===================================================== */

  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 30,
    backgroundColor: "#FFFFFF",
  },

  loadingMark: {
    width: 64,
    height: 64,
    borderRadius: 20,
    backgroundColor: "#E31B23",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },

  loadingMarkText: {
    color: "#FFFFFF",
    fontSize: 26,
    fontWeight: "900",
  },

  loadingTitle: {
    color: "#111111",
    fontSize: 24,
    fontWeight: "800",
  },

  loadingText: {
    marginTop: 8,
    color: "#8A8A8A",
    textAlign: "center",
    fontSize: 14,
  },

  loader: {
    marginTop: 18,
  },

  /* ===================================================== */
  /* HEADER */
  /* ===================================================== */

  topHeader: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 18,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },

  headerContent: {
    flex: 1,
    paddingRight: 12,
  },

  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 11,
  },

  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#E31B23",
    marginRight: 7,
  },

  statusText: {
    color: "#E31B23",
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1.4,
  },

  greeting: {
    color: "#777777",
    fontSize: 14,
    marginBottom: 4,
  },

  title: {
    color: "#111111",
    fontSize: 34,
    fontWeight: "900",
    letterSpacing: -1.2,
  },

  subtitle: {
    color: "#777777",
    fontSize: 14,
    marginTop: 5,
  },

  appMark: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: "#E31B23",
    alignItems: "center",
    justifyContent: "center",
  },

  appMarkText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "900",
  },

  /* ===================================================== */
  /* AUDIO CARD */
  /* ===================================================== */

  audioCard: {
    marginHorizontal: 16,
    marginBottom: 18,
    padding: 18,
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E9E9E9",
    shadowColor: "#000000",
    shadowOffset: {
      width: 0,
      height: 6,
    },
    shadowOpacity: 0.07,
    shadowRadius: 18,
    elevation: 3,
  },

  audioCardTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },

  audioCardTitleBox: {
    flex: 1,
    paddingRight: 12,
  },

  audioEyebrow: {
    color: "#E31B23",
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.3,
  },

  audioCardTitle: {
    marginTop: 5,
    color: "#111111",
    fontSize: 21,
    lineHeight: 27,
    fontWeight: "800",
  },

  readyBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: "#FFF1F2",
  },

  readyDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: "#E31B23",
    marginRight: 5,
  },

  readyBadgeText: {
    color: "#E31B23",
    fontSize: 8,
    fontWeight: "900",
    letterSpacing: 0.6,
  },

  /* ===================================================== */
  /* AUDIO PLAYER */
  /* ===================================================== */

  playerRow: {
    marginTop: 20,
    padding: 14,
    borderRadius: 18,
    backgroundColor: "#F7F7F7",
    borderWidth: 1,
    borderColor: "#EEEEEE",
    flexDirection: "row",
    alignItems: "center",
  },

  playButton: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#E31B23",
    alignItems: "center",
    justifyContent: "center",
  },

  playButtonDisabled: {
    backgroundColor: "#D9D9D9",
  },

  playButtonPressed: {
    transform: [
      {
        scale: 0.94,
      },
    ],
    opacity: 0.85,
  },

  playButtonText: {
    color: "#FFFFFF",
    fontSize: 20,
    fontWeight: "800",
    marginLeft: 2,
  },

  playerInfo: {
    flex: 1,
    marginLeft: 14,
  },

  playerTitle: {
    color: "#111111",
    fontSize: 14,
    fontWeight: "800",
  },

  playerSubtitle: {
    color: "#8A8A8A",
    fontSize: 11,
    marginTop: 4,
  },

  audioStatus: {
    alignItems: "flex-end",
    marginLeft: 8,
  },

  audioStatusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#E31B23",
    marginBottom: 5,
  },

  audioStatusText: {
    color: "#999999",
    fontSize: 8,
    fontWeight: "800",
    letterSpacing: 0.7,
  },

  audioUnavailable: {
    marginTop: 10,
    color: "#999999",
    fontSize: 11,
  },

  /* ===================================================== */
  /* SCRIPT */
  /* ===================================================== */

  scriptSection: {
    marginTop: 20,
  },

  scriptSectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  scriptEyebrow: {
    color: "#999999",
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.2,
  },

  scriptLanguage: {
    color: "#AAAAAA",
    fontSize: 8,
    fontWeight: "800",
    letterSpacing: 1,
  },

  scriptText: {
    marginTop: 10,
    color: "#242424",
    fontSize: 16,
    lineHeight: 29,
  },

  scriptFooter: {
    marginTop: 18,
    paddingTop: 13,
    borderTopWidth: 1,
    borderTopColor: "#EEEEEE",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  scriptFooterText: {
    flex: 1,
    color: "#AAAAAA",
    fontSize: 10,
  },

  scriptFooterStatus: {
    color: "#999999",
    fontSize: 9,
    fontWeight: "700",
  },

  /* ===================================================== */
  /* GENERATION CARD */
  /* ===================================================== */

  generationCard: {
    marginHorizontal: 16,
    marginBottom: 18,
    padding: 18,
    borderRadius: 22,
    backgroundColor: "#F8F8F8",
    borderWidth: 1,
    borderColor: "#ECECEC",
  },

  generationHeader: {
    flexDirection: "row",
    alignItems: "center",
  },

  generationIcon: {
    width: 42,
    height: 42,
    borderRadius: 13,
    backgroundColor: "#FFF1F2",
    borderWidth: 1,
    borderColor: "#FFD7DA",
    alignItems: "center",
    justifyContent: "center",
  },

  generationIconText: {
    color: "#E31B23",
    fontSize: 19,
    fontWeight: "800",
  },

  generationHeaderText: {
    flex: 1,
    marginLeft: 12,
  },

  generationEyebrow: {
    color: "#E31B23",
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.2,
  },

  generationTitle: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "800",
    marginTop: 3,
  },

  generationDescription: {
    marginTop: 14,
    color: "#777777",
    fontSize: 13,
    lineHeight: 21,
  },

  generateButton: {
    minHeight: 50,
    marginTop: 17,
    borderRadius: 14,
    backgroundColor: "#E31B23",
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    paddingHorizontal: 18,
  },

  generateButtonDisabled: {
    opacity: 0.65,
  },

  generateButtonPressed: {
    opacity: 0.82,
    transform: [
      {
        scale: 0.99,
      },
    ],
  },

  generateButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "800",
    marginLeft: 8,
  },

  generationErrorBox: {
    marginTop: 13,
    padding: 12,
    borderRadius: 12,
    backgroundColor: "#FFF1F2",
    borderWidth: 1,
    borderColor: "#FFD5D8",
  },

  generationErrorTitle: {
    color: "#E31B23",
    fontSize: 12,
    fontWeight: "800",
  },

  generationError: {
    color: "#777777",
    fontSize: 11,
    lineHeight: 17,
    marginTop: 4,
  },

  /* ===================================================== */
  /* INTELLIGENCE CARD */
  /* ===================================================== */

  intelligenceCard: {
    marginHorizontal: 16,
    marginBottom: 24,
    padding: 18,
    borderRadius: 22,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E9E9E9",
    shadowColor: "#000000",
    shadowOffset: {
      width: 0,
      height: 5,
    },
    shadowOpacity: 0.05,
    shadowRadius: 14,
    elevation: 2,
  },

  intelligenceHeader: {
    flexDirection: "row",
    alignItems: "center",
  },

  intelligenceIcon: {
    width: 42,
    height: 42,
    borderRadius: 13,
    backgroundColor: "#FFF1F2",
    borderWidth: 1,
    borderColor: "#FFD7DA",
    alignItems: "center",
    justifyContent: "center",
  },

  intelligenceIconText: {
    color: "#E31B23",
    fontSize: 19,
    fontWeight: "800",
  },

  intelligenceHeaderText: {
    flex: 1,
    marginLeft: 12,
  },

  intelligenceLabel: {
    color: "#999999",
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.2,
  },

  intelligenceTitle: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "800",
    marginTop: 2,
  },

  onlineBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 20,
    backgroundColor: "#F7F7F7",
  },

  onlineDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: "#E31B23",
    marginRight: 5,
  },

  onlineText: {
    color: "#888888",
    fontSize: 8,
    fontWeight: "900",
  },

  intelligenceDescription: {
    marginTop: 16,
    color: "#777777",
    fontSize: 13,
    lineHeight: 20,
  },

  statsRow: {
    flexDirection: "row",
    marginTop: 18,
    paddingVertical: 14,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: "#EEEEEE",
  },

  statBox: {
    flex: 1,
    alignItems: "center",
  },

  statValue: {
    color: "#111111",
    fontSize: 20,
    fontWeight: "900",
  },

  statLabel: {
    color: "#999999",
    fontSize: 8,
    fontWeight: "800",
    letterSpacing: 0.8,
    marginTop: 3,
  },

  statDivider: {
    width: 1,
    backgroundColor: "#EEEEEE",
  },

  analyzedRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 14,
  },

  analyzedIcon: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: "#FFF1F2",
    alignItems: "center",
    justifyContent: "center",
  },

  analyzedIconText: {
    color: "#E31B23",
    fontSize: 10,
    fontWeight: "900",
  },

  analyzedText: {
    marginLeft: 8,
    color: "#999999",
    fontSize: 11,
  },

  briefingLoading: {
    marginTop: 18,
    flexDirection: "row",
    alignItems: "center",
  },

  briefingLoadingText: {
    flex: 1,
    marginLeft: 10,
    color: "#888888",
    fontSize: 12,
    lineHeight: 18,
  },

  briefingErrorBox: {
    marginTop: 16,
  },

  briefingErrorTitle: {
    color: "#E31B23",
    fontWeight: "700",
    fontSize: 14,
  },

  briefingError: {
    marginTop: 5,
    color: "#888888",
    fontSize: 12,
    lineHeight: 18,
  },

  smallRetryButton: {
    alignSelf: "flex-start",
    marginTop: 12,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: "#E31B23",
  },

  smallRetryText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
  },

  /* ===================================================== */
  /* SECTIONS */
  /* ===================================================== */

  categoriesWrapper: {
    paddingHorizontal: 16,
  },

  sectionHeader: {
    paddingHorizontal: 4,
    marginBottom: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
  },

  sectionEyebrow: {
    color: "#E31B23",
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.3,
  },

  sectionTitle: {
    color: "#111111",
    fontSize: 24,
    fontWeight: "900",
    marginTop: 3,
  },

  sectionCount: {
    color: "#999999",
    fontSize: 11,
    marginBottom: 3,
  },

  /* ===================================================== */
  /* CATEGORY */
  /* ===================================================== */

  categoryCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#EAEAEA",
  },

  categoryHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingBottom: 12,
  },

  categoryIcon: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: "#F7F7F7",
    borderWidth: 1,
    borderColor: "#EAEAEA",
    alignItems: "center",
    justifyContent: "center",
  },

  categoryIconText: {
    color: "#E31B23",
    fontSize: 16,
    fontWeight: "800",
  },

  categoryNameBox: {
    flex: 1,
    marginLeft: 10,
  },

  categoryTitle: {
    color: "#111111",
    fontSize: 16,
    fontWeight: "800",
  },

  categoryEnglish: {
    color: "#999999",
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 1,
    marginTop: 2,
  },

  storyCountBadge: {
    minWidth: 28,
    height: 28,
    borderRadius: 10,
    backgroundColor: "#F7F7F7",
    alignItems: "center",
    justifyContent: "center",
  },

  storyCountText: {
    color: "#E31B23",
    fontSize: 11,
    fontWeight: "800",
  },

  storyCard: {
    flexDirection: "row",
    paddingVertical: 13,
    borderTopWidth: 1,
    borderTopColor: "#F1F1F1",
  },

  storyNumber: {
    width: 32,
    paddingTop: 2,
  },

  storyNumberText: {
    color: "#BBBBBB",
    fontSize: 10,
    fontWeight: "900",
  },

  storyContent: {
    flex: 1,
  },

  storyTitle: {
    color: "#222222",
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "600",
  },

  storyMeta: {
    marginTop: 7,
    flexDirection: "row",
    alignItems: "center",
  },

  storySource: {
    color: "#999999",
    fontSize: 10,
    flex: 1,
  },

  storyArrow: {
    color: "#E31B23",
    fontSize: 15,
    fontWeight: "700",
  },

  emptyCategory: {
    borderTopWidth: 1,
    borderTopColor: "#F1F1F1",
    paddingTop: 12,
  },

  emptyText: {
    color: "#888888",
    fontSize: 12,
    lineHeight: 18,
  },

  /* ===================================================== */
  /* LATEST NEWS */
  /* ===================================================== */

  latestHeader: {
    paddingHorizontal: 20,
    marginTop: 14,
    marginBottom: 12,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
  },

  latestTitle: {
    color: "#111111",
    fontSize: 24,
    fontWeight: "900",
    marginTop: 3,
  },

  liveSourceBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: "#F7F7F7",
  },

  liveDotSmall: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: "#E31B23",
    marginRight: 5,
  },

  liveSourceText: {
    color: "#888888",
    fontSize: 8,
    fontWeight: "900",
    letterSpacing: 0.8,
  },

  /* ===================================================== */
  /* NEWS */
  /* ===================================================== */

  newsCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 16,
    marginHorizontal: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#EAEAEA",
  },

  newsTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },

  source: {
    color: "#E31B23",
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.7,
  },

  openArrow: {
    color: "#E31B23",
    fontSize: 16,
  },

  newsTitle: {
    marginTop: 9,
    color: "#111111",
    fontSize: 17,
    lineHeight: 24,
    fontWeight: "700",
  },

  description: {
    marginTop: 8,
    color: "#666666",
    fontSize: 13,
    lineHeight: 20,
  },

  date: {
    marginTop: 12,
    color: "#AAAAAA",
    fontSize: 10,
  },

  pressedCard: {
    opacity: 0.65,
    transform: [
      {
        scale: 0.99,
      },
    ],
  },

  /* ===================================================== */
  /* EMPTY */
  /* ===================================================== */

  emptyNews: {
    alignItems: "center",
    paddingVertical: 50,
    paddingHorizontal: 30,
  },

  emptyNewsIcon: {
    width: 52,
    height: 52,
    borderRadius: 18,
    backgroundColor: "#FFF1F2",
    borderWidth: 1,
    borderColor: "#F5D0D3",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 14,
  },

  emptyNewsIconText: {
    color: "#E31B23",
    fontSize: 22,
  },

  emptyNewsTitle: {
    color: "#111111",
    fontSize: 16,
    fontWeight: "800",
  },

  emptyNewsText: {
    marginTop: 5,
    color: "#888888",
    fontSize: 12,
  },

  /* ===================================================== */
  /* ERROR */
  /* ===================================================== */

  errorScreen: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 30,
  },

  errorIcon: {
    width: 58,
    height: 58,
    borderRadius: 20,
    backgroundColor: "#FFF1F2",
    borderWidth: 1,
    borderColor: "#F5B7BB",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 18,
  },

  errorIconText: {
    color: "#E31B23",
    fontSize: 24,
    fontWeight: "900",
  },

  errorTitle: {
    color: "#111111",
    fontSize: 20,
    fontWeight: "800",
    marginBottom: 8,
  },

  errorText: {
    color: "#777777",
    textAlign: "center",
    lineHeight: 20,
    marginBottom: 20,
  },

  retryButton: {
    backgroundColor: "#E31B23",
    paddingHorizontal: 24,
    paddingVertical: 13,
    borderRadius: 13,
  },

  retryText: {
    color: "#FFFFFF",
    fontWeight: "800",
    fontSize: 13,
  },
});
