import { useMemo } from "react";
import { View } from "react-native";
import { EmptyState, OfflineBanner, Text } from "@aylal/ui";
import type { I18n } from "@aylal/i18n";
import { buildMapViewModel, type MapInput } from "./mapViewModel";

interface MapProps extends MapInput {
  i18n: I18n;
}

// The MapLibre RN layer consumes vm.features with the bundled local tiles and fonts.
export function MapScreen({ i18n, ...input }: MapProps) {
  const vm = useMemo(() => buildMapViewModel(input), [input.parcels, input.online]);
  const t = (key: string) => i18n.t(key);
  return (
    <View testID="map.root" style={{ flex: 1 }}>
      {vm.showOfflineBanner ? <OfflineBanner label={t("home.offlineBanner")} /> : null}
      <Text variant="heading" label={t("map.title")} locale={i18n.locale} />
      {vm.state === "empty" ? (
        <View testID="map.state.empty">
          <EmptyState label={t("map.empty")} actionLabel={t("home.state.emptyAction")} />
        </View>
      ) : (
        <View testID={`map.parcels.${vm.features.length}`} accessibilityLabel={t("map.title")} style={{ flex: 1 }} />
      )}
    </View>
  );
}
