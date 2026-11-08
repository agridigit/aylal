"""Deterministic identifiers of F4: the server derives the F6 operation id of an irrigation event (the client never chooses it)."""
import uuid

NS_F4 = uuid.UUID("5c1d6a4e-8f0b-4c53-9a5e-0f4a7e2b9d31")


def operation_id_for(farm_id: uuid.UUID, event_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(NS_F4, f"{farm_id}:{event_id}")
