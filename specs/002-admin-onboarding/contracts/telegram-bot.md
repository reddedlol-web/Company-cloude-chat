# Contract: Admin & Onboarding Commands

**Feature**: `002-admin-onboarding`  
**Version**: 1.0.0  
**Extends**: `001-company-telegram-bot/contracts/telegram-bot.md`

## Deep link onboarding

### `/start invite_{token}`

**Trigger**: Пользователь переходит по ссылке `https://t.me/{bot}?start=invite_{token}`

**Flow (no password)**:
1. Validate token (exists, active, not expired, uses available)
2. If user already allowed → «Вы уже имеете доступ»
3. Register user in `registered_users`
4. Increment invite `use_count`, insert `invite_redemption`
5. Notify admins
6. Welcome message

**Flow (with password)**:
1. Steps 1–2 as above
2. FSM state `AwaitingInvitePassword` → «Введите пароль приглашения»
3. User sends text → verify bcrypt hash
4. On success → register; on failure → «Неверный пароль» (max 3 attempts)

**Success response**:
```text
✅ Добро пожаловать, {name}!
Задавайте вопросы по документам компании.
Лимит сегодня: {limit} вопросов.
```

**Error responses**:

| Condition | Message |
|---|---|
| Invalid/expired/revoked token | `❌ Приглашение недействительно или истекло. Обратитесь к администратору.` |
| Max uses reached | `❌ Это приглашение уже использовано максимальное число раз.` |
| Wrong password | `🔒 Неверный пароль. Осталось попыток: {n}` |
| Too many password attempts | `⛔ Слишком много попыток. Попробуйте позже или запросите новое приглашение.` |
| User blocked | `⛔ Ваш доступ заблокирован.` |

---

## Admin commands

**Access**: All commands below require `is_admin(user_id)` from `ADMIN_USER_IDS`.

### `/invite`

**Subcommands**:

#### `/invite create`

**Interactive flow** (или флаги в одной команде для power users):
```text
/invite create label=Маркетинг password=summer2026 days=14 uses=5
```

**Response**:
```text
🔗 Приглашение создано: «Маркетинг»
Ссылка: https://t.me/CompanyBot?start=invite_xK9mP2qR
Срок: до 13.07.2026 | Использований: 0/5
Пароль: summer2026
```

#### `/invite list`

**Response**:
```text
📋 Активные приглашения:
1. Маркетинг — 2/5 — до 13.07 — invite_xK9m...
2. HR onboarding — 0/1 — до 06.07 — invite_aB3c...
```

#### `/invite revoke <token>`

**Response (success)**:
```text
🚫 Приглашение invite_xK9mP2qR отозвано.
```

---

### `/users`

**Response**:
```text
👥 Пользователи (12):
• @ivanov — ID 123456 — с 01.06 — сегодня 3/20
• @petrov — ID 789012 — с 15.06 — сегодня 0/20
...
```

Pagination: inline buttons `◀️ 1/3 ▶️`

---

### `/user <telegram_id>`

**Response**:
```text
👤 @ivanov (123456)
Регистрация: 01.06.2026 via «Маркетинг»
Статус: активен
Сегодня: 3/20 | Всего запросов: 47
Последний запрос: 29.06 14:32 UTC
```

---

### `/user block <telegram_id>`

**Response**:
```text
🚫 Пользователь 123456 заблокирован.
```

### `/user unblock <telegram_id>`

**Response**:
```text
✅ Пользователь 123456 разблокирован.
```

---

## Admin notification (outbound)

**Trigger**: Successful invite redemption

**Target**: `ADMIN_NOTIFY_CHAT_ID` or DM to each `ADMIN_USER_IDS`

**Message**:
```text
🆕 Новый пользователь: @ivanov (123456)
Приглашение: «Маркетинг» | 29.06.2026 10:15 UTC
```

---

## Modified: `/start` (no parameter)

**Unauthorized user** (updated message):
```text
⛔ У вас нет доступа.
Попросите у администратора ссылку-приглашение или обратитесь в HR.
```
