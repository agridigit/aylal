export type FieldRecord = {
  fields: Record<string, unknown>;
  field_versions: Record<string, number>;
  server_version: number;
};

export type FieldOp = {
  op_id: string;
  author_id: string;
  base_version: number;
  changes: Record<string, unknown>;
  device_clock?: string; // informational only, never used to decide
};

export type FieldConflict = {
  field: string;
  discarded_value: unknown;
  kept_value: unknown;
  discarded_by: string;
  base_version: number;
  server_version: number;
};

export type Resolution = FieldRecord & { has_conflict: boolean; conflicts: FieldConflict[] };

/** Field-by-field merge; the op arriving last wins a contested field. Pure. */
export function resolveFieldConflicts(record: FieldRecord, op: FieldOp): Resolution {
  const serverVersion = record.server_version + 1;
  const fields = { ...record.fields };
  const fieldVersions = { ...record.field_versions };
  const conflicts: FieldConflict[] = [];

  for (const [field, value] of Object.entries(op.changes)) {
    if ((record.field_versions[field] ?? 0) > op.base_version) {
      conflicts.push({
        field,
        discarded_value: record.fields[field],
        kept_value: value,
        discarded_by: op.author_id,
        base_version: op.base_version,
        server_version: serverVersion,
      });
    }
    fields[field] = value;
    fieldVersions[field] = serverVersion;
  }

  return {
    fields,
    field_versions: fieldVersions,
    server_version: serverVersion,
    has_conflict: conflicts.length > 0,
    conflicts,
  };
}
