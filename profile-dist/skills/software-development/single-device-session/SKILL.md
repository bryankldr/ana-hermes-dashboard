---
name: single-device-session
description: Enforce one account per device with revoke and reclaim.
version: 0.1.0
author: System (system), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [session, auth, directus, flutter, single-device]
    related_skills: [systematic-debugging, requesting-code-review]
---

# Single-Device Session Skill

Enforces 1 account = 1 active device for Directus + Flutter apps. Covers session registration, heartbeat, revocation, reclaim via server-side NPK verification, and sync-before-logout ordering.

## When to Use

- Implementing or fixing device_sessions collection with single-active constraints.
- Handling `RECORD_NOT_UNIQUE` on `sessions_device_id` / `device_sessions` POST after revoke.
- Adding NPK verification against `directus_users` for revoked-device reclaim.
- Wiring heartbeat, token refresh gating, and auto-logout on revoked status.

Don't use for: generic OAuth flows without device binding, or server-configurable unique indexes (use DB constraint instead).

## Prerequisites

- Directus collections `device_sessions` and `directus_users` exist; `device_sessions` fields: `id`, `user_id`, `device_id`, `status` (`active`/`cooldown`/`revoked`), `session_version`, `last_seen_at`, `revoke_reason`, `revoked_at`.
- Flutter deps: `dio`, `shared_preferences`, `device_info_plus`, `package_info_plus`, `uuid`, `flutter_background_service`.
- `DeviceInfoService.getDeviceId()` returns hardware ID (`ANDROID_ID` / `identifierForVendor`) with UUID fallback persisted to `SharedPreferences`.
- `DioService.baseUrl` is single source via `String.fromEnvironment('API_BASE_URL', defaultValue: 'https://...')`.

## How to Run

- Session ops go through `SessionManager` singleton and `DioService.authenticatedRequest()` (skip guard only for `device_sessions` and `/auth/`).
- Verify with `terminal(command="flutter analyze 2>&1 | tail -n 20", timeout=90)`.
- Inspect `lib` vs `lib_backup` before deducing regressions: `terminal(command="diff -rq lib lib_backup | head -n 100")`.

## Procedure

1. **Device ID:** Use hardware ID first. On Android read `androidInfo.id` (reject `9774d56d682e549c` bug value), on iOS `identifierForVendor`. Persist to `device_id` key; fallback to generated UUID only if hardware unavailable.
2. **Registration (registerSession):** GET `device_sessions` filtered by `user_id` + `status in [active, cooldown]`. If same `device_id` and no `revokeReason`, PATCH `last_seen_at` + increment `session_version`. If different device or explicit reason, PATCH old row to `revoked`/`cooldown` per reason, then POST new row. Tag errors containing `RECORD_NOT_UNIQUE` or `sessions_device_id` or `has to be unique` as `RECORD_NOT_UNIQUE` in `_sessionError` for UI branching.
3. **Reclaim after revoked:** On POST 400 `RECORD_NOT_UNIQUE`, show revoked dialog — "Perangkat dicabut hak aksesnya". Prompt for NPK code. Call `verifyNpk(input)` -> GET `/users/me?fields=id,npk` then fallback GET `/users/<id>?fields=id,npk`; compare trimmed server `npk` to input (from `directus_users`, never from local `getah_daftar_tpg`). If match, `reclaimWithNpk`: GET all `device_sessions` for user with `status in [active, cooldown]`, PATCH each `device_id != current` to `revoked` (`npk_verified_reclaim`), then try PATCH existing row for this `device_id` to `active` (clear `revoke_reason`/`revoked_at`/`cooldown_until`, bump `session_version`). On PATCH failure, DELETE old row then POST new. Persist validity flags and restart heartbeat.
4. **Heartbeat:** `Timer.periodic(Duration(minutes:1))` PATCH `last_seen_at` + `session_version`. On response `status == revoked`, stop timer, run sync-before-revoke before setting revoked flag (so guard still allows), then persist `last_session_revoked` + reason/time, clear session, call `performLogoutOnRevoke` (which does `DioService().dispose()` to cancel token refresh timer), navigate via global `navigatorKey` to `/login`.
5. **Sync-before-revoke:** Call `SyncTransaction.instance.syncTransactionIncremental().timeout(Duration(seconds:30))` best-effort before setting `_isSessionRevoked = true`. Fail-open to logout on timeout/error.
6. **Guards:** In `DioService.authenticatedRequest`, block non-session paths when `isRevokedLocal()` or `!isSessionAllowedForRequest()` (4s timeout, fail-open). Token refresh timer (`_startRefreshTimer` ~10m) must check `isRevokedLocal` and `isSessionAllowedForRequest` and cancel if revoked. `AppLifecycleManager` on `resumed` calls `validateSession`.
7. **Login UI:** After `login()` success, set `has_logged_in_before=true`, `has_logged_out=false`, then `checkExistingSessionOnDifferentDevice()` + dialog or `registerSession()`. On `false` return, check `isRecordNotUniqueError`; if true trigger NPK reclaim dialog, on success continue to `/dashboard`, else stay on login with Snackbar. Fail-closed — never navigate on registration failure.

## Pitfalls

- Unique constraint survives revoke — revoked row still occupies the unique index on `device.sessions_device_id`, so re-creating the same `device_id` without PATCH/DELETE yields `RECORD_NOT_UNIQUE` on every retry; handle by reactivating the existing row rather than looping POST.
- Verify NPK server-side only — local table `getah_daftar_tpg.npk_online` is stale/offline cache and bypasses server truth; always query `directus_users.npk` via `/users/me` or `/users/<id>` with `fields=id,npk`.
- Guard ordering matters — setting revoked flag before sync causes the Dio guard to cancel the sync itself; sequence is stop heartbeat, sync with timeout, then set flag, then clear and logout.
- Hardware ID vs ephemeral UUID — generating a fresh UUID per install creates a new unique key that collides with the old revoked row on server; prefer `ANDROID_ID`/`identifierForVendor` so reinstall hits the same `device_id` and can be reactivated.
- Token refresh prolongs revoked JWT — without gating the periodic refresh on session validity, a revoked device keeps refreshing until expiry; cancel timer in `performLogoutOnRevoke` and gate `_startRefreshTimer` on session checks.
- Swallowing registration errors continues login — returning `true` on `getCurrentUserId() == null` or catching and ignoring `authenticatedRequest` lets a revoked client proceed to dashboard; fail-closed and surface the error.
- Env-only server address — hardcoding `baseUrl` in `auth_helpers`, `photo_service`, `network_stability_guard` drifts from `DioService.baseUrl`; derive all from `DioService.baseUrl` and change via `--dart-define=API_BASE_URL=...`.

## Verification

- `flutter analyze` shows no issues (unused var `isWrongNpk` is a common residual — remove it).
- Login on revoked device shows "Perangkat Dicabut" dialog, wrong NPK stays blocked, correct NPK (matching `directus_users.npk`) revokes other devices and recreates/reactivates session then navigates to dashboard.
- Revoked device heartbeat triggers sync log `Sync transaksi sebelum auto-logout revoked` within 30s then auto-logout and `last_session_revoked` persisted for next login banner.
- `grep -rn RECORD_NOT_UNIQUE lib --include='*.dart'` hits only `session_manager.dart` marker and login branching.
