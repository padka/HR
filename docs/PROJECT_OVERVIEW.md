# Project Overview

RecruitSmart Maxpilot is a recruiting CRM/ATS for candidate intake, verification, scheduling, recruiter coordination, and provider integrations.

## Business Purpose

The system moves candidates from provider-specific entry points into a controlled recruiting funnel:
- identify and verify the candidate;
- collect candidate journey state;
- route candidates through tests and scheduling;
- prevent dead ends when no slots are available;
- give recruiters/admins a single operational surface for follow-up.

## Candidate Journey

The candidate enters through a public route or provider launch:
- public campaign route redirects to the candidate flow;
- verification starts through Telegram, MAX, or HH depending on campaign configuration;
- verified candidate state is resolved through shared candidate-access contracts;
- the candidate can book an available interview slot;
- if no future slot is available, the candidate can submit manual availability for recruiter follow-up.

The no-slot fallback is required for scale readiness. A candidate must never finish verification/Test1 and land in a dead end.

## Recruiter/Admin Journey

Recruiters and admins use the React admin SPA hosted by the FastAPI admin UI:
- view candidate pipeline and details;
- manage slots and manual scheduling;
- review manual availability requests;
- send or retry messages;
- inspect HH sync and integration state;
- use AI advisory surfaces where enabled.

Server-side scoping, CSRF, auth, and safe-error behavior are authoritative. Client state is not trusted for identity or permissions.

## Verification Providers

Supported provider surfaces:
- Telegram: live messaging runtime and candidate entry channel.
- MAX: bounded pilot launch/webhook/mini-app surface over shared candidate-access backend contracts.
- HH: OAuth/API provider for candidate or vacancy-related workflows and sync.

Provider failures must degrade into controlled states. Raw provider secrets and sensitive callback parameters must never be logged.

## Slots And Manual Availability

Slot booking relies on server-side reservation and assignment logic:
- future available slots should be monitored by campaign;
- double booking must be prevented;
- idempotency should protect retry paths;
- manual availability captures candidate-preferred windows when no slot is available;
- ambiguous free text, such as "after 18:00" without a date hint, must not be stored as a precise appointment.

## HH Sync

HH sync jobs track outbound/inbound work, retry behavior, forbidden states, and retention summaries. A persistent HH 403 is a controlled integration state, not an unhandled worker storm.

## Messaging

Telegram is the current live messaging runtime. MAX is bounded-pilot only. Future channels must reuse shared candidate contracts and must not fork Test1, booking, or scheduling business logic.
