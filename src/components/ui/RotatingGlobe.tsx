import { useCallback } from 'react';
import { StyleSheet, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import Svg, { Circle, Defs, Ellipse, Path, RadialGradient, Stop } from 'react-native-svg';
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import { useMotionReduced } from './Motion';

const land = [
  'M18 81 C30 55 49 45 65 51 C79 57 76 70 89 77 C97 82 94 94 82 98 C68 103 63 119 52 119 C42 118 45 101 34 97 C24 94 14 91 18 81Z',
  'M105 39 C125 28 150 34 163 48 C174 60 168 71 155 74 C143 78 142 89 132 94 C119 99 108 89 110 77 C112 66 97 55 105 39Z',
  'M142 110 C158 101 179 108 183 122 C186 134 170 145 159 142 C148 139 151 126 140 121 C135 118 136 113 142 110Z',
];

function MapLayer({ size }: { size: number }) {
  return <Svg width={size} height={size} viewBox="0 0 200 200">
    {land.map((path, index) => <Path key={path} d={path} fill={index === 1 ? '#FFFFFF' : '#DCDCDC'} opacity={0.9} />)}
    <Path d="M22 141 C50 129 78 134 96 151 C106 161 97 174 80 171 C60 168 53 154 34 156 C21 157 13 149 22 141Z" fill="#F7F7F7" opacity={0.76} />
  </Svg>;
}

/** Code-native rotating globe. The map wraps continuously inside a shaded sphere. */
export function RotatingGlobe({ size = 220, active = true }: { size?: number; active?: boolean }) {
  const reduced = useMotionReduced();
  const rotation = useSharedValue(0);

  useFocusEffect(useCallback(() => {
    cancelAnimation(rotation);
    rotation.set(0);
    if (active && !reduced) {
      rotation.set(withRepeat(withTiming(1, {
        duration: 10_000,
        easing: Easing.linear,
      }), -1, false));
    }
    return () => cancelAnimation(rotation);
  }, [active, reduced, rotation]));

  const mapMotion = useAnimatedStyle(() => ({
    transform: [{ translateX: -size * rotation.get() }],
  }));

  return <View
    accessible={false}
    accessibilityElementsHidden
    importantForAccessibility="no-hide-descendants"
    style={[styles.stage, { width: size + 44, height: size + 44 }]}
  >
    <View style={[styles.orbit, { width: size + 34, height: size * 0.46, borderRadius: size }]} />
    <View style={[styles.sphere, { width: size, height: size, borderRadius: size / 2 }]}>
      <Svg width={size} height={size} viewBox="0 0 200 200" style={StyleSheet.absoluteFill}>
        <Defs>
          <RadialGradient id="sphere" cx="32%" cy="24%" rx="75%" ry="78%">
            <Stop offset="0" stopColor="#5A5A5A" />
            <Stop offset="0.42" stopColor="#1B1B1B" />
            <Stop offset="1" stopColor="#000000" />
          </RadialGradient>
        </Defs>
        <Circle cx="100" cy="100" r="99" fill="url(#sphere)" />
      </Svg>
      <Animated.View style={[styles.mapStrip, { width: size * 2, height: size }, mapMotion]}>
        <MapLayer size={size} />
        <MapLayer size={size} />
      </Animated.View>
      <Svg pointerEvents="none" width={size} height={size} viewBox="0 0 200 200" style={StyleSheet.absoluteFill}>
        <Ellipse cx="100" cy="100" rx="98" ry="31" fill="none" stroke="#FFFFFF" strokeOpacity={0.22} strokeWidth="1" />
        <Ellipse cx="100" cy="100" rx="54" ry="98" fill="none" stroke="#FFFFFF" strokeOpacity={0.18} strokeWidth="1" />
        <Ellipse cx="100" cy="100" rx="21" ry="98" fill="none" stroke="#FFFFFF" strokeOpacity={0.12} strokeWidth="1" />
        <Path d="M17 49 C59 66 141 66 183 49 M17 151 C59 134 141 134 183 151" fill="none" stroke="#FFFFFF" strokeOpacity={0.12} strokeWidth="1" />
        <Circle cx="100" cy="100" r="98.5" fill="none" stroke="#FFFFFF" strokeOpacity={0.72} strokeWidth="1.2" />
        <Ellipse cx="69" cy="52" rx="28" ry="13" fill="#FFFFFF" opacity={0.12} rotation="-28" origin="69, 52" />
      </Svg>
    </View>
  </View>;
}

const styles = StyleSheet.create({
  stage: { alignItems: 'center', justifyContent: 'center' },
  orbit: { position: 'absolute', borderWidth: 1, borderColor: '#BEBEBE', transform: [{ rotate: '-16deg' }] },
  sphere: {
    overflow: 'hidden',
    backgroundColor: '#000000',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 18 },
    shadowOpacity: 0.3,
    shadowRadius: 26,
    elevation: 14,
  },
  mapStrip: { position: 'absolute', top: 0, left: 0, flexDirection: 'row', opacity: 0.74 },
});
