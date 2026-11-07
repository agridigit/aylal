import { Home } from "../src/screens/Home/Home";
import { useLocale } from "./_layout";

export default function Index() {
  const { i18n, setLocale } = useLocale();
  return (
    <Home
      i18n={i18n}
      isLoading={false}
      error={null}
      isOffline={false}
      itemCount={0}
      onChangeLanguage={setLocale}
      onRetry={() => {}}
      onAddItem={() => {}}
      onOpenTrialRecord={() => {}}
    />
  );
}
