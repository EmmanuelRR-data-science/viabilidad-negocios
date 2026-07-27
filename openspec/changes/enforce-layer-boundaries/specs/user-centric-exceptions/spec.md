## ADDED Requirements

### Requirement: User-facing errors use natural language exceptions
The API SHALL expose failures to end users through dedicated exception types under `app/exceptions/` that carry clear, actionable Spanish messages. Technical exception messages, Python tracebacks, and raw `str(exc)` MUST NOT be returned as HTTP `detail` to clients.

#### Scenario: Analytics validation or upstream failure
- **WHEN** an analytics flow fails due to geocoding, missing data, or an unexpected infrastructure error
- **THEN** the HTTP response body uses a user-centric message from the exceptions layer (or middleware mapping) and does not echo the raw exception string

#### Scenario: Technical detail remains in logs
- **WHEN** such a failure occurs
- **THEN** the server logs the technical exception with stack context via `logger.exception` (or equivalent) without exposing that text to the client

### Requirement: Exception hierarchy covers common failure classes
`app/exceptions/` SHALL define a base user-facing exception and specialized types for at least: resource not found, payment/authorization required, external dependency failure, and domain validation failure. Routers and services MUST raise these types instead of ad-hoc `HTTPException(detail=str(exc))` for business/infra failures.

#### Scenario: Missing order maps to not-found user exception
- **WHEN** a report or payment flow references an order that does not exist
- **THEN** a typed not-found user exception is raised and mapped to an appropriate HTTP status with a friendly message

### Requirement: Middleware complements typed exceptions
The existing user-friendly middleware MAY continue to catch uncaught infrastructure exceptions, but handlers that can anticipate failure modes MUST raise typed `app.exceptions` rather than relying solely on the catch-all.

#### Scenario: Anticipated Bedrock/S3 failure path
- **WHEN** a service detects a known AWS/client failure while generating a report
- **THEN** it raises a typed external-dependency user exception instead of letting a raw SDK error surface as `detail`

### Requirement: Admin surfaces friendly flash or page errors
Admin SHALL provide an `exceptions/` (or equivalent) mapping so ingest/schema/query failures show Spanish user messages in flashes or page errors and MUST NOT display raw `str(err)` from database or ingest exceptions to operators without a friendly wrapper.

#### Scenario: Ingest ZIP failure message
- **WHEN** a manual ingest fails due to a database or shapefile error
- **THEN** the operator sees a clear Spanish message and the technical error is logged server-side
