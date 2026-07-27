## ADDED Requirements

### Requirement: Quantitative analysis can be obtained without LLM
The system SHALL provide a way (HTTP endpoint under auth, or documented CLI/script) to obtain the quantitative analysis payload (demography, NSE, competitors, allies, scores, afluencia as applicable by tier) as structured JSON **without** invoking the LLM/FODA step.

#### Scenario: Debug dump skips FODA
- **WHEN** an authorized operator requests quantitative debug export for a location/rubro (or runs the documented script)
- **THEN** the response/file contains the quantitative JSON and does not call the LLM provider

### Requirement: Optional tabular export for quantitative payload
The system SHOULD support exporting the same quantitative payload (or a curated subset) to Excel for human inspection during QA. If Excel export is deferred, the JSON dump remains mandatory and Excel is listed as a follow-up task with explicit scope.

#### Scenario: Excel export when enabled
- **WHEN** Excel export is implemented and requested
- **THEN** the file contains key quantitative sections suitable for review without opening the PDF/IA narrative

### Requirement: Debug path is not a substitute for paid report product
The quantitative debug export MUST NOT bypass payment entitlement for customer-facing paid PDF downloads. Debug access SHALL be limited (admin/dev auth, `DEV_MODE`, or internal flag) as documented.

#### Scenario: Paid PDF still requires approval
- **WHEN** a normal customer without approved payment requests a paid PDF
- **THEN** access remains denied regardless of debug export availability
