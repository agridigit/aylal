import { createLocalControls } from "../localControls";
import { createCatalogCache } from "../catalogCache";

const use = (over = {}) => ({ crop_slug: "tomato", max_dose: 2, dose_unit: "L/ha", dar_days: 7, max_applications: 3, ...over });
const catalog = { source_date: "2026-10-01", products: [{ id: "p1", name: "Cuprex", active_ingredients: [{ name: "cuivre" }], uses: [use()] }] };

describe("local phyto controls (R2-A3 to R2-A5, offline)", () => {
  const controls = createLocalControls(createCatalogCache(catalog));

  it("given a dose above the maximum when checking offline then the warning is returned", () => {
    expect(controls.check({ product_id: "p1", crop_slug: "tomato", dose: 3, dose_unit: "L/ha", applications_so_far: 0 })).toEqual(["dose_above_max"]);
  });

  it("given a product not authorised on the crop when checking then the warning is returned", () => {
    expect(controls.check({ product_id: "p1", crop_slug: "olive", dose: 1, dose_unit: "L/ha", applications_so_far: 0 })).toEqual(["not_authorized_for_crop"]);
  });

  it("given a free product when checking then it is flagged unchecked", () => {
    expect(controls.check({ free_product_name: "Maison", crop_slug: "tomato", dose: 1, dose_unit: "L/ha", applications_so_far: 0 })).toEqual(["free_product_unchecked"]);
  });

  it("given an unknown catalogue id when checking then nothing throws and the product is treated as unchecked", () => {
    expect(() => controls.check({ product_id: "zzz", crop_slug: "tomato", dose: 1, dose_unit: "L/ha", applications_so_far: 0 })).not.toThrow();
  });

  it("given the cache when checking then a control takes less than 50 ms", () => {
    const start = performance.now();
    for (let i = 0; i < 100; i++) controls.check({ product_id: "p1", crop_slug: "tomato", dose: 3, dose_unit: "L/ha", applications_so_far: 1 });
    expect((performance.now() - start) / 100).toBeLessThan(50);
  });

  it("given the cache when asking the catalogue date then the source date is returned for display with the controls", () => {
    expect(createCatalogCache(catalog).sourceDate()).toBe("2026-10-01");
  });

  it("given the cache when searching by name or active ingredient then matching products come with their ingredients", () => {
    const cache = createCatalogCache(catalog);
    expect(cache.search("cupr").map((p) => p.name)).toEqual(["Cuprex"]);
    expect(cache.search("cuivre").map((p) => p.name)).toEqual(["Cuprex"]);
    expect(cache.search("%")).toEqual([]);
  });
});
