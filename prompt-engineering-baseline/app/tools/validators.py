# Source history: Raj Kumar (a3ef3a6); see source-history.json.
import re
from datetime import datetime, timezone


def validate_coordinates(lat: float | None, lon: float | None) -> dict:
    errors = []
    if lat is None or lon is None:
        errors.append("lat and lon are required")
    else:
        if not (-90 <= lat <= 90):
            errors.append(f"lat {lat} out of range [-90, 90]")
        if not (-180 <= lon <= 180):
            errors.append(f"lon {lon} out of range [-180, 180]")
    return {"valid": len(errors) == 0, "errors": errors}


def validate_timestamp(ts: str | None) -> dict:
    if not ts:
        return {"valid": False, "errors": ["timestamp is required"]}
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        drift_s = abs((now - dt).total_seconds())
        if drift_s > 300:
            return {"valid": False, "errors": [f"timestamp drift {drift_s:.0f}s exceeds 300s limit"]}
        return {"valid": True, "errors": []}
    except ValueError:
        return {"valid": False, "errors": [f"timestamp '{ts}' is not valid ISO8601"]}


def validate_device_id(device_id: str | None) -> dict:
    if not device_id:
        return {"valid": False, "errors": ["device_id is required"]}
    if not re.match(r"^[a-zA-Z0-9_\-]{4,64}$", device_id):
        return {"valid": False, "errors": ["device_id must be 4–64 alphanumeric/dash/underscore chars"]}
    return {"valid": True, "errors": []}


def validate_location_request(params: dict) -> dict:
    results = {
        "coordinates": validate_coordinates(params.get("lat"), params.get("lon")),
        "timestamp": validate_timestamp(params.get("timestamp")),
        "device_id": validate_device_id(params.get("device_id")),
    }
    all_errors = [e for r in results.values() for e in r["errors"]]
    return {"valid": len(all_errors) == 0, "checks": results, "all_errors": all_errors}


def classify_error_code(code: str) -> dict:
    mapping = {
        "400": {"category": "client", "description": "Invalid request parameters", "action": "Check coordinate ranges and required fields"},
        "401": {"category": "auth", "description": "Authentication failed", "action": "Verify token validity and expiry"},
        "403": {"category": "quota", "description": "Quota exceeded", "action": "Check dashboard for quota usage"},
        "404": {"category": "config", "description": "Device not found", "action": "Verify device_id is registered in portal"},
        "422": {"category": "client", "description": "Missing required parameter", "action": "Check required_fields in error response body"},
        "429": {"category": "rate_limit", "description": "Rate limited", "action": "Implement backoff; check Retry-After header"},
        "500": {"category": "server", "description": "Internal server error", "action": "Retry with exponential backoff"},
        "503": {"category": "availability", "description": "Service unavailable", "action": "Check status page; retry after maintenance window"},
    }
    return mapping.get(str(code), {"category": "unknown", "description": "Unknown error", "action": "Contact support with full request/response"})
