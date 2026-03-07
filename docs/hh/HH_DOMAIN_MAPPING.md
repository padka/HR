# HH Domain Mapping

## Candidate
### CRM entity
`backend/domain/candidates/models.py::User`

### HH linkage needed
- `resume_id`
- `topic_id / negotiation_id`
- `vacancy_id`
- `employer_id`
- `manager_id`
- `resume_url`

### Recommended persistence
- keep legacy `users.hh_*` fields for compatibility only
- create `candidate_external_identities` as primary linkage store for new integration

## Vacancy
### CRM entity
`backend/domain/models.py::Vacancy`

### HH linkage needed
- `external_vacancy_id`
- `employer_id`
- `manager_account_id`
- `external_url`
- title snapshot / raw payload

### Recommended persistence
`external_vacancy_bindings`

## Negotiation
### CRM meaning
External lifecycle object for response/invitation per `resume + vacancy`

### HH identifiers
- `topic_id` / `nid`
- `resume_id`
- `vacancy_id`
- `employer_state`
- collection name
- available actions snapshot

### Recommended persistence
`hh_negotiations`

## Recruiter / Manager
### CRM entity
`backend/domain/models.py::Recruiter`

### HH entity
Employer manager + manager account

### Recommended persistence
Store on `hh_connections`:
- `manager_id`
- `manager_account_id`
- `principal_type/principal_id`

Do not directly overload local recruiter record with HH token fields.

## Resume snapshot
### Why
CRM needs stable imported copy for support, audit, AI enrichment and future resume refresh.

### Recommended persistence
`hh_resume_snapshots`
- `external_resume_id`
- `payload_json`
- `content_hash`
- `source_updated_at`
- `fetched_at`

## Deduplication rules
Priority order:
1. exact external negotiation id
2. exact `source + resume_id`
3. guarded fallback on normalized phone/email when business-approved
4. never dedupe by HH URL string only

## Raw vs normalized storage
### Raw payload
Store full upstream JSON for:
- resume snapshots
- negotiation snapshots
- webhook deliveries
- connection profile payload

### Normalized fields
Store search/filter fields explicitly:
- external ids
- employer/manager ids
- employer state
- sync status
- timestamps

## Mapping strategy
### Recommended
- CRM stage -> desired recruiter intent
- intent -> HH runtime action candidate set
- HH action -> resulting HH employer state
- resulting HH state -> CRM external-state badge

### Not recommended
- static `CRM stage -> HH state` hardcode as primary integration logic
