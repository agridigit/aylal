import { useEffect } from "react";
import { View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { Button, Card, Text } from "@aylal/ui";
import type { I18n } from "@aylal/i18n";
import { buildShowcase } from "./showcaseViewModel";
import { buildExport } from "../../perf/measuresExport";

interface ShowcaseProps {
  i18n: I18n;
  reduceMotion: boolean;
  fps: number | null;
  onExport: () => void;
}

export function Showcase({ i18n, reduceMotion, fps, onExport }: ShowcaseProps) {
  const vm = buildShowcase({ reduceMotion });
  const progress = useSharedValue(vm.animated ? 0 : 1);
  const duration = vm.animations[0]?.durationMs ?? 0;
  useEffect(() => {
    progress.value = withTiming(1, { duration });
  }, [duration]);
  const style = useAnimatedStyle(() => ({ opacity: progress.value, transform: [{ scale: 0.9 + 0.1 * progress.value }] }));
  const t = (key: string) => i18n.t(key);
  const verdict = buildExport(fps);
  return (
    <View testID="showcase.root" style={{ flex: 1, gap: 16, padding: 16 }}>
      <Animated.View style={style}>
        <Card>
          <Text variant="heading" label={t("showcase.title")} locale={i18n.locale} />
        </Card>
      </Animated.View>
      <View testID="measures.export">
        <Button variant="secondary" label={t("measures.export")} onPress={onExport} />
      </View>
      <View testID="measures.verdict.fps">
        <Text variant="caption" label={t(`measures.${verdict}`)} locale={i18n.locale} />
      </View>
    </View>
  );
}
