# HH Executive Summary

## What HH API can realistically give RecruitSmart
- employer OAuth integration
- stable external identities for resume / vacancy / negotiation / employer / manager account
- import of vacancies and responses/invitations
- action-driven lifecycle sync
- webhook notifications and reconciliation hooks

## What is risky / should not be core in MVP
- full chat sync through deprecated negotiation message methods
- static hardcoded HH status mapping
- relying on collections as stable stages
- link-only identity model

## Recommended architecture
- separate `HH Integration Module`
- hybrid source-of-truth model
- action-first orchestration
- webhook + polling hybrid
- encrypted connection storage
- sync logs / retry / manual re-sync from day one

## Recommended MVP
1. Employer OAuth.
2. Encrypted connection storage.
3. Foundation tables for candidate/vacancy HH identities.
4. Idempotent HH webhook receiver.
5. Admin connection status endpoints.
6. Keep current legacy `hh_sync` running while new module grows.

## Hypotheses to validate first in code
1. OAuth flow works cleanly with current admin auth/session model.
2. HH webhook receiver can operate securely via per-connection URL key.
3. Connection metadata from `/me` + `/manager_accounts/mine` is enough to anchor later imports.
4. Current DB model can absorb external identity tables without breaking existing candidate flows.
