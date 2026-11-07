import { z } from "zod";

type Position = number[];

export function isValidPolygon(coordinates: Position[][]): boolean {
  if (coordinates.length === 0) return false;
  return coordinates.every((ring) => {
    if (ring.length < 4) return false;
    if (!ring.every((p) => p.length === 2 && Math.abs(p[0]!) <= 180 && Math.abs(p[1]!) <= 90)) {
      return false;
    }
    const first = ring[0]!;
    const last = ring[ring.length - 1]!;
    return first[0] === last[0] && first[1] === last[1];
  });
}

export const PolygonGeometry = z
  .object({
    type: z.literal("Polygon"),
    coordinates: z.array(z.array(z.array(z.number()))).min(1),
  })
  .refine((g) => isValidPolygon(g.coordinates), { message: "invalid_geometry" })
  .meta({ title: "PolygonGeometry" });

export const ParcelCreate = z
  .object({
    name: z.string().min(1).max(80),
    geometry: PolygonGeometry,
    vigor: z.number().min(0).max(1),
  })
  .meta({ title: "ParcelCreate" });
