# Implementation Plan: Админ и самостоятельная регистрация сотрудников

**Branch**: `002-admin-onboarding` | **Date**: 2026-06-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-admin-onboarding/spec.md`

## Summary

Расширение существующего Telegram-бота: админ создаёт invite-ссылки (с опциональным паролем) прямо в чате с ботом; сотрудники регистрируются через deep link `?start=invite_TOKEN`; whitelist хранится в SQLite с fallback на `ALLOWED_USER_IDS`; админ видит список пользователей и получает уведомления в служебный чат. Без отдельной веб-админки — всё в Telegram.

## Technical Context

**Language/Version**: Python 3.11+ (как в 001)

**Primary Dependencies**: aiogram 3.x, bcrypt (хеш паролей invite), существующие `src/db`, `src/config`

**Storage**: SQLite — новые таблицы `invites`, `registered_users`, `invite_redemptions`; совместимость с `daily_usage`, `query_logs`

**Testing**: pytest — unit (invite validation, password hash, auth merge), integration (full onboarding flow)

**Target Platform**: Тот же Docker-контейнер, long polling

**Project Type**: Расширение single backend service

**Performance Goals**: Регистрация ≤2 с; `/users` до 50 записей ≤1 с

**Constraints**: Пароли только hashed; invite-токены криптостойкие (secrets.token_urlsafe); без новых внешних сервисов

**Scale/Scope**: ≤50 пользователей, ≤20 активных invite, 1–3 админа

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution в template-состоянии. Применяем interim gates из 001:

| Gate | Status | Notes |
|---|---|---|
| Simplicity (YAGNI) | ✅ PASS | Нет веб-админки; команды бота + SQLite |
| Testability | ✅ PASS | Unit + integration для invite flow |
| Security | ✅ PASS | Hashed passwords, secure tokens, rate limit на ввод пароля |
| Observability | ✅ PASS | Лог регистраций, admin notify |
| Scope control | ✅ PASS | Только Telegram; extends 001, не переписывает |

**Post-design re-check**: Все gates pass. Единственное усложнение — динамический whitelist вместо чистого env; оправдано требованием самообслуживания.

## Project Structure

### Documentation (this feature)

```text
specs/002-admin-onboarding/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── telegram-bot.md  # Admin + onboarding commands
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (changes to existing layout)

```text
src/
├── bot/
│   ├── handlers/
│   │   ├── commands.py       # + /invite, /users, /user
│   │   └── onboarding.py     # NEW: /start invite_* flow, password FSM
│   └── middleware/
│       └── auth.py           # MODIFY: is_allowed = env OR sqlite, check blocked
├── db/
│   ├── models.py             # + invites, registered_users schema
│   └── repository.py         # + invite/user CRUD
├── config.py                 # + BOT_USERNAME, ADMIN_NOTIFY_CHAT_ID, invite defaults
└── services/
    └── invite.py             # NEW: token gen, validation, redeem logic

tests/
├── unit/
│   ├── test_invite.py        # NEW
│   └── test_auth.py          # UPDATE: dynamic whitelist
└── integration/
    └── test_onboarding_flow.py  # NEW
```

**Structure Decision**: Новый модуль `src/services/invite.py` для бизнес-логики; handler `onboarding.py` с aiogram FSM для ввода пароля. Минимальные изменения в существующем auth middleware.

## Recommended Implementation Approach

### Поток для админа

1. Админ: `/invite create` → бот спрашивает: метка (опц.), пароль (опц.), срок, лимит использований.
2. Бот отвечает готовой ссылкой + текстом для копирования в корпоративный чат:
   ```text
   🔗 Приглашение «Отдел маркетинга» (до 5 чел., до 14.07.2026):
   https://t.me/CompanyBot?start=invite_xK9mP2qR
   Пароль: summer2026
   ```
3. Админ кидает ссылку в командный чат Slack/Telegram/почту.

### Поток для сотрудника

1. Клик по ссылке → Telegram открывает бота с `/start invite_xK9mP2qR`.
2. Если invite с паролем → FSM: «Введите пароль приглашения».
3. Успех → «Добро пожаловать! Лимит: 20 вопросов/день».
4. Уведомление в `ADMIN_NOTIFY_CHAT_ID`.

### Почему этот вариант

| Критерий | Deep link + bot commands | Веб-форма | Ручной .env |
|---|---|---|---|
| Удобство админа | ✅ Всё в Telegram | Нужен хостинг UI | ❌ SSH/деплой |
| Удобство сотрудника | ✅ 1 клик | 2+ шага | ❌ Ждать админа |
| Безопасность | ✅ Пароль + срок + лимит | ✅ | ⚠️ Статично |
| Сложность разработки | Низкая | Высокая | Уже есть |

## Complexity Tracking

> Нет нарушений gates.

## Implementation Phases (for /speckit-tasks)

### Phase A: Schema & invite service
- Миграция SQLite: `invites`, `registered_users`, `invite_redemptions`
- `src/services/invite.py`: create, validate, redeem, revoke
- bcrypt для паролей

### Phase B: Auth middleware update
- `is_allowed()` = env whitelist OR active registered_user
- `is_blocked()` check
- Сохранить `is_admin()` из env

### Phase C: Bot handlers
- `onboarding.py`: deep link `/start invite_*`, FSM password
- `commands.py`: `/invite create|list|revoke`, `/users`, `/user`, `/user block|unblock`
- Admin notify on registration

### Phase D: Tests & docs
- Unit + integration tests
- Обновить `.env.example`, `docs/deploy.md`, README

## Artifacts Generated

| Artifact | Path | Status |
|---|---|---|
| Feature spec | `specs/002-admin-onboarding/spec.md` | ✅ |
| Research | `specs/002-admin-onboarding/research.md` | ✅ |
| Data model | `specs/002-admin-onboarding/data-model.md` | ✅ |
| Contracts | `specs/002-admin-onboarding/contracts/telegram-bot.md` | ✅ |
| Quickstart | `specs/002-admin-onboarding/quickstart.md` | ✅ |
| Tasks | `specs/002-admin-onboarding/tasks.md` | ✅ (implemented) |
