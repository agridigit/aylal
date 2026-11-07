import { readFileSync } from "node:fs";
import { join } from "node:path";
import { TRIAL_RECORD_COLUMNS } from "../powersyncSchema";

describe("PowerSync client schema", () => {
  it("given the server model then trial_records columns match it (id is implicit)", () => {
    const models = readFileSync(join(__dirname, "../../../../../services/api/app/db/models.py"), "utf8");
    const block = models.split("class TrialRecord(Base):")[1]!.split("\nclass ")[0]!;
    const serverCols = [...block.matchAll(/^    (\w+): Mapped/gm)].map((m) => m[1]).filter((c) => c !== "id");
    expect(Object.keys(TRIAL_RECORD_COLUMNS).sort()).toEqual([...serverCols].sort());
  });
});
