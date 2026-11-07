export const DELETION_GRACE_DAYS = 30;

export type OwnedFarmInfo = { farm_id: string; name: string; role: string; other_members: number };

/** Exactly 30 days after the confirmed request (UTC). */
export function deletionDeadline(requestedAt: Date): Date {
  return new Date(requestedAt.getTime() + DELETION_GRACE_DAYS * 86_400_000);
}

/** Farms owned with other members: the owner is warned before confirming. */
export function deletionImpact(farms: readonly OwnedFarmInfo[]): { farm_id: string; name: string; other_members: number }[] {
  return farms
    .filter((f) => f.role === "owner" && f.other_members > 0)
    .map(({ farm_id, name, other_members }) => ({ farm_id, name, other_members }));
}
