/** Client columns of trial_records (id is implicit); mirrors services/api/app/db/models.py. */
export const TRIAL_RECORD_COLUMNS = {
  farm_id: "text",
  author_id: "text",
  title: "text",
  note: "text",
  quantity: "real",
  created_at: "text",
  updated_at: "text",
  server_version: "integer",
  field_versions: "text",
  deleted_at: "text",
  has_conflict: "integer",
} as const;

/** Client columns of parcels (id is implicit); area_calc_ha and status_summary are server-owned. */
export const PARCEL_COLUMNS = {
  farm_id: "text",
  name: "text",
  geometry: "text",
  area_calc_ha: "real",
  area_declared_ha: "real",
  irrigation: "text",
  greenhouse: "integer",
  soil: "text",
  source: "text",
  gps_accuracy_m: "real",
  status_summary: "text",
  created_by: "text",
  archived_at: "text",
  purge_after: "text",
  merged_into_id: "text",
  server_version: "integer",
  field_versions: "text",
  updated_at: "text",
} as const;
