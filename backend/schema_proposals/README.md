# Automatic briefing preferences — review proposal

`automatic_briefing_preferences.sql` is a local, review-only schema proposal. It has
not been applied to Supabase and is not a numbered migration. The Supabase CLI is not
installed in this workspace, so the project migration workflow must create the eventual
migration with the CLI after review. Do not run this proposal against production.

## Changes proposed

- Add `profiles.daily_reminder_enabled`, defaulting to `false` for every existing user.
- Add `profiles.auto_play_when_open`, defaulting to `false`.
- Add `profiles.delivery_schedule`, defaulting to `daily`, with `weekdays` as the other value.
- Queue a notification only when a ready briefing has stored audio, the profile opts in,
  the date matches the chosen schedule, and the account is still active.
- Delay the durable notification until the saved local delivery time if audio is ready
  early. Suppress the reminder when the briefing becomes ready more than two hours late;
  the saved audio remains available in the app.
- Cancel pending notifications when the account disables reminders. An FCM message
  already claimed/in-flight cannot be recalled.
- Recompute today's pending notification time when the user changes their reminder,
  weekday, timezone, or delivery-time preferences; enabling a reminder can enqueue the
  already-ready briefing for today if it is still within the two-hour reminder window.

The proposal does not insert trials, alter subscription state, touch article/audio data,
modify RLS policies or client grants, or add any public RPC. Existing profile ownership
and the service-only notification queue remain the authorization boundary.

## Preflight and compatibility

Before an approved staging migration, verify the connected project is exactly
`wwtntxknfjagdjdgiaxu`, verify the currently deployed notification function definition,
and check all existing profile timezones/hours/minutes. The proposal aborts if timezones
or delivery values are invalid. Existing profiles receive safe opt-out defaults; saved
categories, delivery time/timezone, subscriptions, briefings, device tokens and audio are
preserved. The application/backend changes that read the added columns must deploy only
after the database migration succeeds.

## Rollback

Disable `SCHEDULER_ENABLED` and `PUSH_DELIVERY_ENABLED` first. Roll back the application
code. Keep the three new profile columns so any saved user choices are preserved. If the
trigger behavior must be reverted, restore the prior reviewed function definition and
remove only the opt-out trigger; do not delete notification or briefing rows. Dropping
columns later would discard preferences and requires separate approval.

## Verification required before enabling workers

Use isolated staging test accounts and rollback-only checks to verify: daily and weekday
selection, timezone/DST due times, early and late ready briefings, opt-out before queue,
opt-out after queue, inactive/deleted account cancellation, duplicate device prevention,
service-only outbox access, and that no notification is enqueued for a briefing without
stored audio. Then test actual generation/storage/FCM only after explicit provider, cost,
worker and push approval. No live check was run for this local proposal.
