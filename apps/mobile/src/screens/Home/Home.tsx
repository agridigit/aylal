import { useEffect, useMemo } from "react";
import { View } from "react-native";
import { Button, EmptyState, ErrorState, OfflineBanner, Skeleton, Text } from "@aylal/ui";
import { LOCALES, type I18n, type Locale } from "@aylal/i18n";
import { speak } from "../../voice/speak";
import { createStartupMark } from "../../perf/startupMark";
import { layoutFor } from "./direction";
import { buildHomeViewModel, type HomeInput } from "./homeViewModel";

export const startupMark = createStartupMark();

interface HomeProps extends HomeInput {
  i18n: I18n;
  onChangeLanguage: (locale: Locale) => void;
  onRetry: () => void;
  onAddItem: () => void;
  onOpenTrialRecord: () => void;
  onOpenMap?: () => void;
  onOpenShowcase?: () => void;
}

export function Home(props: HomeProps) {
  const { i18n } = props;
  const vm = useMemo(() => buildHomeViewModel(props), [props.isLoading, props.error, props.isOffline, props.itemCount]);
  const layout = layoutFor(i18n.locale);
  const t = (key: string) => i18n.t(key);

  useEffect(() => {
    startupMark.homeDisplayed();
  }, []);

  const onPress = (id: string) => {
    if (id === "home.speak") speak(t("home.title"), i18n.locale);
    else if (id === "home.openTrialRecord") props.onOpenTrialRecord();
    else if (id === "home.openMap") props.onOpenMap?.();
    else if (id === "home.openShowcase") props.onOpenShowcase?.();
    else props.onChangeLanguage(id.replace("lang.", "") as Locale);
  };

  const extraButtons: { id: string }[] = [];
  if (props.onOpenMap) extraButtons.push({ id: "home.openMap" });
  if (props.onOpenShowcase) extraButtons.push({ id: "home.openShowcase" });

  return (
    <View style={{ flex: 1, gap: 16, padding: 16, direction: layout.writingDirection }}>
      <View testID="home.title">
        <Text variant="heading" label={t("home.title")} locale={i18n.locale} />
        <Text variant="caption" label={t("home.subtitle")} locale={i18n.locale} />
      </View>
      {vm.blocks.map((b) => {
        const message = t(b.messageKey ?? "");
        switch (b.component) {
          case "OfflineBanner":
            return (
              <View key={b.component} testID="home.offlineBanner">
                <OfflineBanner label={message} />
              </View>
            );
          case "Skeleton":
            return (
              <View key={b.component} testID="home.state.loading" accessibilityLabel={message}>
                <Skeleton variant="block" />
              </View>
            );
          case "ErrorState":
            return (
              <View key={b.component} testID="home.state.error">
                <ErrorState variant="page" label={message} solutionLabel={t(b.solutionKey ?? "")} actionLabel={t(b.action?.labelKey ?? "")} />
              </View>
            );
          case "EmptyState":
            return (
              <View key={b.component} testID="home.state.empty">
                <EmptyState label={message} actionLabel={t(b.action?.labelKey ?? "")} />
              </View>
            );
          default:
            return <Text key={b.component} label={message} locale={i18n.locale} />;
        }
      })}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {vm.buttons.map((b) => (
          <View key={b.id} testID={b.id} style={{ minWidth: b.minWidth, minHeight: b.minHeight }}>
            <Button
              variant={b.id === `lang.${i18n.locale}` ? "primary" : "secondary"}
              label={t(b.labelKey)}
              onPress={() => onPress(b.id)}
            />
          </View>
        ))}
        {extraButtons.map((b) => (
          <View key={b.id} testID={b.id} style={{ minWidth: 48, minHeight: 48 }}>
            <Button variant="secondary" label={t(b.id)} onPress={() => onPress(b.id)} />
          </View>
        ))}
      </View>
    </View>
  );
}

export const HOME_LOCALES = LOCALES;
