import { mkdirSync, writeFileSync } from "node:fs";
import { z } from "zod";
import { FarmCreate } from "./schemas/farm";
import { ParcelCreate } from "./schemas/parcel";
import { TrialRecordCreate } from "./schemas/trial_record";

const outDir = new URL("../schema/", import.meta.url);
mkdirSync(outDir, { recursive: true });

const targets = { trial_record: TrialRecordCreate, parcel: ParcelCreate, farm: FarmCreate };
for (const [name, schema] of Object.entries(targets)) {
  const json = z.toJSONSchema(schema, { io: "input", target: "draft-7", unrepresentable: "any" });
  writeFileSync(new URL(`${name}.json`, outDir), JSON.stringify(json, null, 2) + "\n");
}
