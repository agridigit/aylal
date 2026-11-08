"""Scoped access to irrigation (G1): the SAME predicate as F3 (`visible_parcels`), so REST, sync, export, calculations and
reminders agree. An invisible parcel (other farm, unknown, archived, not assigned to a worker) is a 404 before the role check."""
from app.monitoring.access import farm_access, parcel_access, parcel_readable, visible_parcels

__all__ = ["farm_access", "parcel_access", "parcel_readable", "visible_parcels"]
