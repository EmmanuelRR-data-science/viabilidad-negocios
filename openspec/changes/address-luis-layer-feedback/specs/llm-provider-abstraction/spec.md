## ADDED Requirements

### Requirement: LLM access goes through an interchangeable provider interface
The API SHALL expose LLM capabilities (FODA, category IA, guardrails where applicable) through a provider abstraction in `clients/` (raw/processed or strategy registry) such that the active provider is selected by configuration (e.g. env var), not by hard-wiring call sites to AWS Bedrock.

#### Scenario: Local development without AWS
- **WHEN** `LLM_PROVIDER` (or equivalent) is set to a non-Bedrock provider such as Groq or OpenAI
- **THEN** FODA/report generation can run without AWS credentials or Bedrock network access

#### Scenario: Bedrock remains an optional implementation
- **WHEN** production is configured for Bedrock
- **THEN** the same service-layer FODA orchestration calls the abstraction and the Bedrock adapter is the selected implementation

### Requirement: Services do not import Bedrock-specific SDKs directly
Service modules that need LLM text SHALL call the LLM client abstraction (or `foda_service` which uses that abstraction) and MUST NOT import `boto3` Bedrock APIs directly for generation.

#### Scenario: foda_service uses provider facade
- **WHEN** `generar_analisis_foda` runs
- **THEN** the LLM invoke path goes through the configured provider client, not a Bedrock-only hard dependency at the service layer
