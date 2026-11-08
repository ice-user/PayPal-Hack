"""Validate webhook envelopes and retain only dispute metadata (no buyer data)."""
from datetime import datetime, timezone

DISPUTE_EVENTS = {"CUSTOMER.DISPUTE.CREATED", "CUSTOMER.DISPUTE.UPDATED", "CUSTOMER.DISPUTE.RESOLVED"}
MAX_BODY_BYTES = 1024 * 1024


def timestamp(value: object) -> str:
    if not isinstance(value, str) or len(value) > 64 or "T" not in value:
        raise ValueError("Expected an ISO timestamp with a timezone.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp requires a timezone.")
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Expected an ISO timestamp with a timezone.") from exc


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise ValueError(f"{field} must be a nonempty string of at most 255 characters.")
    return value


def metadata(event: object) -> dict:
    """Project a validated envelope; the original object is used for verification."""
    if not isinstance(event, dict):
        raise ValueError("Webhook must be a JSON object.")
    result = {"event_id": _string(event.get("id"), "id"),
              "event_type": _string(event.get("event_type"), "event_type"),
              "created_at": timestamp(event.get("create_time")), "dispute": None}
    resource = event.get("resource")
    if not isinstance(resource, dict):
        raise ValueError("resource must be an object.")
    if result["event_type"] in DISPUTE_EVENTS:
        dispute = {"dispute_id": _string(resource.get("dispute_id"), "dispute_id")}
        for key in ("status", "dispute_state", "dispute_life_cycle_stage"):
            dispute[key] = None if resource.get(key) is None else _string(resource[key], key)
        dispute["update_time"] = None if resource.get("update_time") is None else timestamp(resource["update_time"])
        result["dispute"] = dispute
    return result
