import { createMeasureSession, fpsFromFrames, EXPORT_LOG_TAG } from "../measureSession";
import { e2eParcels } from "../../screens/Map/e2eParcels";
import { buildMapViewModel } from "../../screens/Map/mapViewModel";

const DEVICE = "emulator aylal-2go (provisoire)";
const session = () => createMeasureSession({ device: DEVICE, build: "test", today: () => "2026-11-07" });

describe("measure session (AC6.1-6.3, provisional emulator values)", () => {
  it("given frame timestamps when computing fps then it is frames per second over the window", () => {
    const ts = Array.from({ length: 61 }, (_, i) => i * (1000 / 60));
    expect(fpsFromFrames(ts)).toBeCloseTo(60, 1);
    expect(fpsFromFrames([0, 100, 200])).toBeCloseTo(10, 5);
  });

  it("given fewer than two frames then fps is unknown, never invented", () => {
    expect(fpsFromFrames([])).toBeNull();
    expect(fpsFromFrames([5])).toBeNull();
  });

  it("given nothing measured then nothing is exported", () => {
    expect(session().export()).toEqual([]);
  });

  it("given startup, map and fps readings then each is exported with its threshold, device and verdict", () => {
    const s = session();
    s.markStartup(2500);
    s.markMapOpened(2400);
    s.recordFps(58);
    const byMetric = Object.fromEntries(s.export().map((m) => [m.metric, m]));
    expect(byMetric.startup_ms).toMatchObject({ value: 2500, threshold: 3000, verdict: "met", device: DEVICE, unit: "ms" });
    expect(byMetric.map_open_ms).toMatchObject({ value: 2400, threshold: 2000, verdict: "not_met" });
    expect(byMetric.fps).toMatchObject({ value: 58, threshold: 60, verdict: "not_met", unit: "fps" });
  });

  it("given a reading when marked twice then the first one is kept (cold start only)", () => {
    const s = session();
    s.markStartup(1000);
    s.markStartup(9000);
    expect(s.export()[0]!.value).toBe(1000);
  });

  it("given an export then the log line carries the tag and a JSON array", () => {
    const s = session();
    s.markStartup(1);
    const line = s.exportLine();
    expect(line.startsWith(`${EXPORT_LOG_TAG} `)).toBe(true);
    expect(JSON.parse(line.slice(EXPORT_LOG_TAG.length + 1))).toHaveLength(1);
  });
});

describe("E2E local parcels", () => {
  it("given the E2E fixture then it provides 50 valid local parcels shown without network", () => {
    const parcels = e2eParcels();
    expect(parcels).toHaveLength(50);
    const vm = buildMapViewModel({ parcels, online: false });
    expect(vm.features).toHaveLength(50);
    expect(vm.requiresNetwork).toBe(false);
    for (const p of parcels) expect(p.vigor).toBeGreaterThanOrEqual(0);
  });
});
