import { LIMITS } from "@aylal/domain/field";
import type { IrrigationMode } from "@aylal/domain/field";
import type { Pt } from "@aylal/domain/geometry";
import { validateDrawn } from "./drawSession";
import type { LocalDb } from "../sync/db";

export type DrawnFieldInput = {
  farm_id: string;
  name: string;
  ring: Pt[];
  source: "draw_taps" | "draw_gps";
  gps_accuracy_m?: number | null;
  irrigation?: IrrigationMode | null;
  greenhouse?: boolean;
  area_declared_ha?: number | null;
};

function uuidv4(): string {
  const b = Array.from({ length: 16 }, () => Math.floor(Math.random() * 256));
  b[6] = ((b[6] as number) & 0x0f) | 0x40;
  b[8] = ((b[8] as number) & 0x3f) | 0x80;
  const h = b.map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** Saves a drawn field locally (queued for upload). area_calc_ha is server-owned: never written here. */
export async function saveDrawnField(db: LocalDb, input: DrawnFieldInput): Promise<string> {
  const name = input.name.trim();
  if (name.length < 1 || name.length > LIMITS.MAX_NAME_LENGTH) throw new Error("name_invalid");
  const v = validateDrawn(input.ring);
  if (!v.ok) throw new Error(v.code);
  const id = uuidv4();
  await db.insert("parcels", {
    id,
    farm_id: input.farm_id,
    name,
    geometry: JSON.stringify({ type: "Polygon", coordinates: [v.ring] }),
    source: input.source,
    gps_accuracy_m: input.gps_accuracy_m ?? null,
    irrigation: input.irrigation ?? null,
    greenhouse: input.greenhouse ? 1 : 0,
    area_declared_ha: input.area_declared_ha ?? null,
  });
  return id;
}
