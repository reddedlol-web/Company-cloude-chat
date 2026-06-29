# Data Model: Админ и самостоятельная регистрация

**Feature**: `002-admin-onboarding`  
**Date**: 2026-06-29  
**Extends**: `001-company-telegram-bot/data-model.md`

## Overview

Добавляются три таблицы в SQLite. Сущность Employee из 001 дополняется динамической регистрацией; env `ALLOWED_USER_IDS` остаётся источником bootstrap-доступа.

---

## Entity: Invite

Приглашение для самостоятельной регистрации.

| Field | Type | Required | Description |
|---|---|---|---|
| id | TEXT | yes | PK, UUID |
| token | TEXT | yes | Уникальный, для deep link (`invite_xK9mP2qR`) |
| password_hash | TEXT | no | bcrypt; NULL = без пароля |
| label | TEXT | no | Человекочитаемая метка («Отдел продаж») |
| created_by | INTEGER | yes | Telegram ID админа |
| max_uses | INTEGER | yes | 0 = безлимит; default 1 |
| use_count | INTEGER | yes | default 0 |
| expires_at | TEXT | yes | ISO UTC |
| status | TEXT | yes | `active`, `revoked`, `expired` |
| created_at | TEXT | yes | ISO UTC |

**Validation**:
- `token` уникален, формат `^[a-zA-Z0-9_-]{8,32}$`
- `max_uses` ≥ 0
- `use_count` ≤ `max_uses` (если max_uses > 0)

**State transitions**:
- `active` + now > expires_at → `expired` (lazy check при redeem)
- Admin revoke → `revoked`
- use_count reaches max_uses → redeem rejected (status остаётся active до expiry)

---

## Entity: RegisteredUser

Сотрудник, зарегистрированный через invite (или синхронизированный из env при первом обращении — опционально v2.1).

| Field | Type | Required | Description |
|---|---|---|---|
| telegram_user_id | INTEGER | yes | PK |
| username | TEXT | no | @handle без @ |
| display_name | TEXT | no | first_name + last_name |
| invite_id | TEXT | no | FK → Invite |
| registered_at | TEXT | yes | ISO UTC |
| is_active | BOOLEAN | yes | default true |
| blocked_at | TEXT | no | UTC если заблокирован |
| blocked_by | INTEGER | no | Admin telegram_id |

**Validation**:
- `telegram_user_id` > 0
- `is_active=false` ⇒ `blocked_at` NOT NULL

**Access rule**:
```
is_allowed(user_id) =
  user_id IN ALLOWED_USER_IDS (env)
  OR (registered_users.is_active AND blocked_at IS NULL)
```

---

## Entity: InviteRedemption

Аудит: кто и когда использовал invite.

| Field | Type | Required | Description |
|---|---|---|---|
| id | INTEGER | yes | PK autoincrement |
| invite_id | TEXT | yes | FK → Invite |
| telegram_user_id | INTEGER | yes | FK → RegisteredUser |
| redeemed_at | TEXT | yes | ISO UTC |

**Unique constraint**: `(invite_id, telegram_user_id)` — один пользователь не может дважды использовать тот же invite.

---

## Entity: PasswordAttempt (ephemeral / SQLite)

Защита от брутфорса пароля invite.

| Field | Type | Required | Description |
|---|---|---|---|
| telegram_user_id | INTEGER | yes | |
| invite_id | TEXT | yes | |
| attempt_count | INTEGER | yes | |
| window_start | TEXT | yes | ISO UTC |

**Unique constraint**: `(telegram_user_id, invite_id)`  
**Rule**: attempt_count ≥ 3 within 15 min → reject further attempts

---

## Schema SQL (migration)

```sql
CREATE TABLE IF NOT EXISTS invites (
    id TEXT PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    label TEXT,
    created_by INTEGER NOT NULL,
    max_uses INTEGER NOT NULL DEFAULT 1,
    use_count INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registered_users (
    telegram_user_id INTEGER PRIMARY KEY,
    username TEXT,
    display_name TEXT,
    invite_id TEXT REFERENCES invites(id),
    registered_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    blocked_at TEXT,
    blocked_by INTEGER
);

CREATE TABLE IF NOT EXISTS invite_redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invite_id TEXT NOT NULL REFERENCES invites(id),
    telegram_user_id INTEGER NOT NULL,
    redeemed_at TEXT NOT NULL,
    UNIQUE (invite_id, telegram_user_id)
);

CREATE TABLE IF NOT EXISTS password_attempts (
    telegram_user_id INTEGER NOT NULL,
    invite_id TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    window_start TEXT NOT NULL,
    PRIMARY KEY (telegram_user_id, invite_id)
);

CREATE INDEX IF NOT EXISTS idx_invites_token ON invites (token);
CREATE INDEX IF NOT EXISTS idx_invites_status ON invites (status);
CREATE INDEX IF NOT EXISTS idx_registered_users_active ON registered_users (is_active);
```

---

## Config additions (BotConfig)

| Variable | Type | Default | Description |
|---|---|---|---|
| BOT_USERNAME | string | — | Для генерации ссылок (или auto from getMe) |
| ADMIN_NOTIFY_CHAT_ID | int | — | Группа для уведомлений о регистрации |
| INVITE_DEFAULT_DAYS | int | 7 | Срок invite по умолчанию |
| INVITE_DEFAULT_MAX_USES | int | 1 | Лимит использований по умолчанию |

---

## Relationships Diagram

```text
Admin (env ADMIN_USER_IDS) 1 ──< Invite (created_by)
Invite 1 ──< InviteRedemption
Invite 1 ──< RegisteredUser (invite_id)
RegisteredUser 1 ──< DailyUsage (existing)
RegisteredUser 1 ──< QueryLog (existing)
```
