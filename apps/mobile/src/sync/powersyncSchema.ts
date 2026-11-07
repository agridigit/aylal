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
