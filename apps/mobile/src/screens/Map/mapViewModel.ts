export interface CachedParcel {
  id: string;
  name: string;
  geometry: { type: "Polygon"; coordinates: number[][][] };
  vigor: number;
}

export interface MapInput {
  parcels: CachedParcel[];
  online: boolean;
}

export function buildMapViewModel(i: MapInput) {
  const features = i.parcels.map((p) => ({
    type: "Feature" as const,
    id: p.id,
    geometry: p.geometry,
    properties: { name: p.name, vigor: p.vigor },
  }));
  return {
    state: features.length === 0 ? ("empty" as const) : ("ready" as const),
    features,
    // Tiles and fonts are bundled on the device: the map never needs the network.
    tileSource: "local" as const,
    fontSource: "local" as const,
    requiresNetwork: false,
    showOfflineBanner: !i.online,
  };
}
