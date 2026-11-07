import { useEffect } from "react";
import { useNetworkState } from "expo-network";
import { MapScreen } from "../src/screens/Map/Map";
import { e2eParcels } from "../src/screens/Map/e2eParcels";
import { mapOpenTimer } from "../src/perf/measureSession";
import { runtimeConfig } from "../src/sync/powersyncRuntime";
import { useLocale } from "./_layout";

// Provisional: until the local parcels table is wired, only E2E builds have a local parcel set.
const PARCELS = runtimeConfig.e2e ? e2eParcels() : [];

export default function MapRoute() {
  const { i18n } = useLocale();
  const network = useNetworkState();
  useEffect(() => mapOpenTimer.stop(), []);
  return <MapScreen i18n={i18n} parcels={PARCELS} online={network.isConnected !== false} />;
}
