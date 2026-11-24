# Integration, Authentication, SDKs and Webhooks — Full Reference

## Authentication

### API Key Authentication
- Header: X-API-Key: gs_your_key_here
- Keys start with prefix gs_
- Used for server-to-server calls
- Generate keys in the developer dashboard
- Keys do not expire unless manually revoked
- Rotate keys: generate new key, update application, revoke old key

### OAuth 2.0
- Flow: client_credentials
- Token endpoint: POST /v1/oauth/token
- Required: client_id, client_secret, grant_type=client_credentials
- Token response: { access_token, token_type: Bearer, expires_in: 3600 }
- Use in header: Authorization: Bearer {access_token}
- Refresh: request new token before expiry (JWT exp claim)
- Available on Professional and Enterprise plans

### JWT Details
- Algorithm: RS256
- Expiry: 3600 seconds (1 hour)
- Claims: sub (client_id), iat, exp, scope
- Verify expiry before each request to avoid 401 errors

### IP Allowlisting
- Available on Enterprise plan
- Configure allowed IP ranges in dashboard
- Requests from non-allowlisted IPs return 403

## SDKs

### iOS SDK
- Language: Swift
- Minimum iOS: 14.0
- Installation: CocoaPods (pod 'LocationSvc') or Swift Package Manager
- Features: directions, autocomplete, reverse geocode, tracking, geofencing
- Background location: supported with NSLocationAlwaysUsageDescription

### Android SDK
- Language: Kotlin and Java
- Minimum API level: 21 (Android 5.0)
- Installation: Maven/Gradle (implementation 'com.locationsvc:android-sdk:2.1.0')
- Features: directions, autocomplete, reverse geocode, tracking, geofencing
- Background location: supported with ACCESS_BACKGROUND_LOCATION permission

### Web SDK
- Language: JavaScript and TypeScript
- Package: @locationsvc/web (npm)
- Installation: npm install @locationsvc/web
- Features: directions, autocomplete, reverse geocode, map rendering
- No tracking or geofencing in Web SDK — use REST API directly

### Server SDKs
- Python: pip install locationsvc (supports all APIs)
- Node.js: npm install @locationsvc/node (supports all APIs)
- Java: Maven com.locationsvc:java-sdk:2.1.0
- Go: go get github.com/locationsvc/go-sdk

## Webhooks

### Setup
- Register webhook URL in dashboard: Settings → Webhooks → Add Endpoint
- URL must be HTTPS (TLS 1.2 or higher)
- Events: geofence.enter, geofence.exit, geofence.dwell, tracking.alert, quota.warning

### Signature Verification
- Header: X-Signature: sha256=hex_digest
- Algorithm: HMAC-SHA256
- Secret: webhook signing secret from dashboard
- Verify: compute HMAC-SHA256 of raw request body using signing secret; compare to header

### Retry Policy
- Retry on: non-2xx response or connection timeout
- Retry schedule: 5s, 30s, 300s (3 attempts total)
- After 3 failures: event marked as failed; visible in dashboard webhook logs
- Manual replay: available in dashboard for failed events within 7 days

### Payload Format
```json
{
  "event": "geofence.enter",
  "timestamp": "2024-01-15T10:30:00Z",
  "device_id": "truck-001",
  "geofence_id": "zone-warehouse-a",
  "location": { "lat": 48.8566, "lon": 2.3522 }
}
```

## Data Residency
- EU region: data stored in Frankfurt (AWS eu-central-1)
- US region: data stored in Virginia (AWS us-east-1)
- APAC region: data stored in Singapore (AWS ap-southeast-1)
- Available on Enterprise plan only
- GDPR compliant; DPA available on request
- Data residency selection: account-level setting, cannot be changed after account creation

## Error Handling Best Practices
- 401: refresh OAuth token or verify API key
- 403: check quota in dashboard; upgrade plan if needed
- 429: implement exponential backoff; respect Retry-After header
- 500: retry up to 3 times with exponential backoff (1s, 2s, 4s)
- 503: check status page at status.locationsvc.com; retry after maintenance window

## Rate Limiting
- Rate limit headers returned on every response:
  - X-RateLimit-Limit: requests per second allowed
  - X-RateLimit-Remaining: requests remaining in current window
  - X-RateLimit-Reset: Unix timestamp when window resets
  - Retry-After: seconds to wait (only on 429 responses)
