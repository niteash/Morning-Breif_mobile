import { Tabs } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MiniPlayer } from '../../../components/PlaybackControls';
import { Type } from '../../../components/ui/primitives';
import { MotionPressable, useMotionReduced } from '../../../components/ui/Motion';
import { usePalette, useCopy } from '../../../features/preferences/PreferencesProvider';
const labels: Record<string, string> = { home: 'ပင်မ', news: 'သတင်း', settings: 'ဆက်တင်' };
const icons: Record<string, string> = { home: '⌂', news: '▤', settings: '⚙' };
export default function MainTabs() {
  const colors = usePalette(), t = useCopy();
  const reduced = useMotionReduced();
  const insets = useSafeAreaInsets();
  return <Tabs screenOptions={{ headerShown: false, animation: reduced ? 'none' : 'fade', sceneStyle: { backgroundColor: colors.background } }} tabBar={({ state, navigation }) => <View style={{ backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border, paddingBottom: Math.max(insets.bottom, 10) }}>
    <MiniPlayer />
    <View style={styles.bar}>
      {state.routes.map((route, i) => <View key={route.key} style={styles.tabSlot}><MotionPressable accessibilityRole="tab" accessibilityLabel={t(labels[route.name])} accessibilityState={{ selected: state.index === i }} onPress={() => {
        const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
        if (!event.defaultPrevented) navigation.navigate(route.name);
      }} style={({ pressed }) => [styles.tab, { backgroundColor: state.index === i ? colors.text : colors.surface, borderColor: state.index === i ? colors.text : colors.border }, pressed && { opacity: 0.68 }]}>
        <Type translate={false} style={{ color: state.index === i ? colors.surface : colors.secondary, fontSize: 24, lineHeight: 28 }}>{icons[route.name]}</Type>
        {state.index === i ? <View accessible={false} style={[styles.activeDot, { backgroundColor: colors.surface }]} /> : null}
      </MotionPressable></View>)}
    </View>
  </View>}>
    <Tabs.Screen name="home" options={{ title: 'ပင်မ' }} />
    <Tabs.Screen name="news" options={{ title: 'သတင်း' }} />
    <Tabs.Screen name="settings" options={{ title: 'ဆက်တင်' }} />
  </Tabs>;
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', paddingHorizontal: 18, paddingTop: 8, gap: 12 },
  tabSlot: { flex: 1 },
  tab: { width: '100%', minHeight: 50, borderRadius: 19, borderWidth: 1, alignItems: 'center', justifyContent: 'center', gap: 2 },
  activeDot: { width: 4, height: 4, borderRadius: 2 },
});
