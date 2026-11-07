"""Rights matrix, mirror of packages/domain/src/roles.ts (shared vectors f1_roles.json)."""

ROLES = ("owner", "manager", "worker")
OWNER_MANAGER = frozenset({"owner", "manager"})
ADMIN_ROLES = OWNER_MANAGER  # roles allowed to write trial records over sync (F0 behaviour)

MATRIX: dict[str, frozenset[str]] = {
    "farm.delete": frozenset({"owner"}),
    "farm.update": OWNER_MANAGER,
    "member.invite": frozenset({"owner"}),
    "member.role_change": frozenset({"owner"}),
    "member.remove": frozenset({"owner"}),
    "parcels.assign": OWNER_MANAGER,
    "record.write": frozenset(ROLES),
    "record.read_all": OWNER_MANAGER,
    "finance.read": OWNER_MANAGER,
}


def can(role: str, action: str) -> bool:
    return role in MATRIX.get(action, frozenset())
