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

export const INVITABLE_ROLES = ["manager", "worker"] as const;

/** Only the owner removes members, and never an owner. */
export function canRemoveMember(actor: string, target: string): boolean {
  return can(actor, "member.remove") && target !== "owner";
}

/** Staff assigns parcels, to workers only. */
export function canAssignParcelsTo(actor: string, target: string): boolean {
  return can(actor, "parcels.assign") && target === "worker";
}
