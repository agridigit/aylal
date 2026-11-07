export const ROLES = ["owner", "manager", "worker"] as const;
export type Role = (typeof ROLES)[number];

const OWNER: Role[] = ["owner"];
const OWNER_MANAGER: Role[] = ["owner", "manager"];
const ALL: Role[] = ["owner", "manager", "worker"];

/** Rights matrix (CPS section 6). Shared vectors: vectors/f1_roles.json. */
export const MATRIX: Record<string, readonly Role[]> = {
  "farm.delete": OWNER,
  "farm.update": OWNER_MANAGER,
  "member.invite": OWNER,
  "member.role_change": OWNER,
  "member.remove": OWNER,
  "parcels.assign": OWNER_MANAGER,
  "record.write": ALL,
  "record.read_all": OWNER_MANAGER,
  "finance.read": OWNER_MANAGER,
};

export function can(role: string, action: string): boolean {
  return (MATRIX[action] ?? []).includes(role as Role);
}
