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
    # F2: every write belongs to owner and manager; a worker only reads its assigned fields
    "field.create": OWNER_MANAGER,
    "field.update": OWNER_MANAGER,
    "field.archive": OWNER_MANAGER,
    "field.restore": OWNER_MANAGER,
    "field.merge": OWNER_MANAGER,
    "field.split": OWNER_MANAGER,
    "season.start": OWNER_MANAGER,
    "season.update": OWNER_MANAGER,
    "crop.create_custom": OWNER_MANAGER,
}


def can(role: str, action: str) -> bool:
    return role in MATRIX.get(action, frozenset())

INVITABLE_ROLES = ("manager", "worker")  # owner is never invitable


def can_remove_member(actor: str, target: str) -> bool:
    """Only the owner removes members, and never an owner."""
    return can(actor, "member.remove") and target != "owner"


def can_assign_parcels_to(actor: str, target: str) -> bool:
    """Staff assigns parcels, to workers only."""
    return can(actor, "parcels.assign") and target == "worker"
