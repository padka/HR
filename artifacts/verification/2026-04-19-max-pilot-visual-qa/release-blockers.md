# Release Blockers

## External Blocker

External blocker: safe non-prod MAX provider proof is not possible from the current workspace because the available local token is rejected by MAX (`/me` and `/subscriptions` return `401 Invalid access_token`), and the canonical pilot env needed for launch/webhook proof (`MAX_ADAPTER_ENABLED`, `MAX_PUBLIC_BOT_NAME`, `MAX_MINIAPP_URL`, `MAX_BOT_API_SECRET`) is not present. Webhook subscription, real send, provider-backed launch, and follow-up proof remain blocked pending valid non-prod MAX credentials and partner-side configuration.

## Evidence

- Local provider probe against `https://platform-api.max.ru/me` returned `401 Invalid access_token`.
- Local provider probe against `https://platform-api.max.ru/subscriptions` returned `401 Invalid access_token`.
- Local runtime/settings inventory still lacks the full canonical pilot set for provider-backed proof.

## Non-Blockers Closed In This Pass

- Runtime/docs truth is synchronized with the mounted `/miniapp`, `/api/max/launch`, `/api/max/webhook`, and shared `/api/candidate-access/*` surfaces.
- `/miniapp` UX gaps for manual review, chat handoff success, booking empty states, booking success, and next-step rendering are closed in code.
- Operator bounded visibility now includes preferred-channel filtering, linked channel badges, compact MAX state chips, and explicit launch-observed state.
- Browser-level visual QA evidence exists under this artifact folder.
