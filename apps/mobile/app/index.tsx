import { useLocalSearchParams } from "expo-router";
import { useNetworkState } from "expo-network";
import { Home } from "../src/screens/Home/Home";
import { debugStateFrom } from "../src/screens/Home/debugState";
import { useLocale } from "./_layout";

const E2E_DEBUG = process.env.EXPO_PUBLIC_E2E === "1";

export default function Index() {
  const { i18n, setLocale } = useLocale();
  const { debugState } = useLocalSearchParams<{ debugState?: string }>();
  const network = useNetworkState();
  const isOffline = network.isConnected === false || network.isInternetReachable === false;
  const debug = debugStateFrom(debugState, E2E_DEBUG);
  return (
    <Home
      i18n={i18n}
      isLoading={debug === "loading"}
      error={debug === "error" ? new Error("debug") : null}
      isOffline={isOffline}
      itemCount={0}
      onChangeLanguage={setLocale}
      onRetry={() => {}}
      onAddItem={() => {}}
      onOpenTrialRecord={() => {}}
    />
  );
}
