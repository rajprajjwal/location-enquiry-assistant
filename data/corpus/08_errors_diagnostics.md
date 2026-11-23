# Error Codes, Diagnostics and Troubleshooting — Full Reference

## HTTP Error Code Reference

### 400 — INVALID_REQUEST / INVALID_COORDINATES
- Meaning: Request contains invalid parameters or malformed coordinates
- Common causes:
  - Latitude outside range -90 to 90
  - Longitude outside range -180 to 180
  - Coordinates in wrong order (lon before lat)
  - Missing required parameter
  - Invalid parameter type (string where number expected)
- Fix: Validate all coordinates before sending; check required parameter list for the API

### 401 — AUTH_FAILED
- Meaning: Authentication failed — API key or OAuth token is invalid or expired
- Common causes:
  - API key revoked or deleted
  - JWT token expired (exp claim in past)
  - Wrong header name (use X-API-Key, not Authorization for API key auth)
  - OAuth token not refreshed before expiry
- Fix: Verify API key in dashboard; refresh OAuth token; check header name

### 403 — QUOTA_EXCEEDED / FORBIDDEN
- Meaning: Monthly quota exceeded or IP not allowlisted
- Common causes:
  - Monthly request quota hit
  - IP allowlisting enabled and request from non-allowlisted IP
  - Feature not available on current plan
- Fix: Check quota in dashboard; upgrade plan; add IP to allowlist

### 404 — NOT_FOUND / DEVICE_NOT_FOUND
- Meaning: Requested resource not found
- Common causes:
  - device_id not registered in portal
  - place_id expired or invalid
  - Endpoint URL typo
- Fix: Verify device_id is registered; re-fetch place_id from autocomplete

### 422 — MISSING_PARAMETER
- Meaning: Required parameter is absent from the request
- Common causes:
  - Required field not included in request body
  - Parameter name misspelled
  - Wrong content-type (must be application/json for POST requests)
- Fix: Check required_fields array in error response body; add missing parameters

### 429 — RATE_LIMITED
- Meaning: Requests per second limit exceeded
- Common causes:
  - Burst of requests exceeding per-second limit
  - No backoff implemented
- Fix: Implement exponential backoff; respect Retry-After header value; reduce request rate

### 500 — INTERNAL_ERROR
- Meaning: Transient server-side error
- Common causes:
  - Temporary infrastructure issue
  - Request triggered edge case in server
- Fix: Retry up to 3 times with exponential backoff (1s, 2s, 4s); if persistent, contact support

### 503 — SERVICE_UNAVAILABLE
- Meaning: Service is in maintenance window or experiencing an incident
- Common causes:
  - Planned maintenance
  - Unplanned incident
- Fix: Check status.locationsvc.com; retry after maintenance window; subscribe to status alerts

## 6-Step Diagnostic Checklist for Location API Errors

### Step 1 — Verify Device Registration
- Check device_id is registered in the developer portal
- Portal: dashboard.locationsvc.com → Devices → Search by device_id
- Unregistered device_id returns 404 DEVICE_NOT_FOUND

### Step 2 — Check Authentication
- Verify API key is active in dashboard (not revoked)
- For OAuth: check JWT exp claim — token must not be expired
- Confirm correct header: X-API-Key for API key, Authorization: Bearer for OAuth
- Test with a simple GET /v1/health request to isolate auth issues

### Step 3 — Validate Timestamp
- Timestamp must be ISO8601 format: YYYY-MM-DDTHH:MM:SSZ
- Timestamp must be within ±5 minutes (300 seconds) of server time
- Drift >300s returns 422 MISSING_PARAMETER with field: timestamp
- Sync device clock with NTP server to prevent drift

### Step 4 — Validate Coordinates
- Latitude: must be between -90 and 90
- Longitude: must be between -180 and 180
- Order: latitude must come before longitude in all parameters
- Precision: use at least 4 decimal places for street-level accuracy
- Common mistake: GPS hardware sometimes returns lon before lat

### Step 5 — Check Account Quota
- Dashboard: dashboard.locationsvc.com → Usage → Current Month
- Check both request count and element count (for Distance Matrix)
- Quota resets on the 1st of each month at 00:00 UTC
- Set up quota alerts at 80% and 95% to avoid unexpected 403 errors

### Step 6 — Review Error Response Body
- Always log the full response body, not just the HTTP status code
- 422 errors include required_fields array listing missing parameters
- 400 errors include error_detail string describing the invalid parameter
- 429 errors include Retry-After header with seconds to wait
- Include X-Request-Id header value when contacting support

## Common Troubleshooting Scenarios

### Scenario: All requests returning 401 since this morning
1. Check if API key was recently rotated or revoked in dashboard
2. If using OAuth: check if token refresh logic is working
3. Verify header name is X-API-Key (not Api-Key or x-api-key — case-insensitive but check spelling)
4. Test with curl: curl -H "X-API-Key: gs_your_key" https://api.locationsvc.com/v1/health

### Scenario: 422 errors on Distance Matrix but not Directions
1. Check required parameters for Distance Matrix: origins (array), destinations (array), mode
2. Verify Content-Type header is application/json for POST request
3. Check origins and destinations are arrays, not strings
4. Review required_fields in error response body

### Scenario: Intermittent 500 errors (1 in 20 requests)
1. Log X-Request-Id for failing requests
2. Check if failures correlate with specific coordinates or parameters
3. Implement retry with exponential backoff
4. If error rate >5% for >15 minutes: escalate to L2 support with X-Request-Id values

### Scenario: Webhook not firing after geofence event
1. Verify webhook URL is HTTPS and returns 2xx
2. Check webhook logs in dashboard for delivery attempts and errors
3. Verify HMAC-SHA256 signature verification is not rejecting valid payloads
4. Test webhook endpoint manually with a POST request
5. Check geofence is active (not paused) in dashboard
