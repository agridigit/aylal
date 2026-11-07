import { useEffect, useState } from "react";
import { AccessibilityInfo } from "react-native";
import { Showcase } from "../src/screens/Showcase/Showcase";
import { fpsFromFrames, measureSession } from "../src/perf/measureSession";
import { useLocale } from "./_layout";

const WINDOW_MS = 1500;

export default function ShowcaseRoute() {
  const { i18n } = useLocale();
  const [reduceMotion, setReduceMotion] = useState(false);
  const [fps, setFps] = useState<number | null>(null);

  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion);
  }, []);

  // JS-thread frame counter over the entry animation: a provisional fps reading.
  useEffect(() => {
    const frames: number[] = [];
    let id = 0;
    const tick = (t: number) => {
      frames.push(t);
      if (t - frames[0]! < WINDOW_MS) {
        id = requestAnimationFrame(tick);
        return;
      }
      const value = fpsFromFrames(frames);
      if (value !== null) {
        measureSession.recordFps(value);
        setFps(value);
      }
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, []);

  return <Showcase i18n={i18n} reduceMotion={reduceMotion} fps={fps} onExport={() => console.log(measureSession.exportLine())} />;
}
