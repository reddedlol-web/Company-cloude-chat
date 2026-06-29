# Research: Админ и самостоятельная регистрация сотрудников

**Feature**: `002-admin-onboarding`  
**Date**: 2026-06-29

## Decision 1: Механизм приглашения

**Decision**: Telegram deep link с параметром `start=invite_{token}`

**Rationale**: Нативный UX Telegram — один клик, бот сразу получает токен в `/start`. Не нужен внешний сайт, OAuth, QR-коды. [Документация Telegram](https://core.telegram.org/bots/features#deep-linking): параметр `start` до 64 символов; наш токен `invite_` + 16 символов urlsafe ≈ 23 символа.

**Alternatives considered**:
- Отдельная веб-страница с формой — лишний хостинг и CORS
- Только пароль без ссылки (`/join PASSWORD`) — хуже UX, пароль утекает в истории чата
- Invite только через CLI — админ не должен иметь SSH

---

## Decision 2: Хранение whitelist

**Decision**: Гибрид — `ALLOWED_USER_IDS` (env, bootstrap) + `registered_users` (SQLite, динамика)

**Rationale**: Существующие пользователи и админы продолжают работать без миграции. Новые — через invite попадают в SQLite. `is_allowed(user_id)` = `user_id in env OR (registered AND NOT blocked)`.

**Alternatives considered**:
- Только SQLite — ломает текущий деплой, нужна миграция env→DB
- Только env — не решает задачу самообслуживания

---

## Decision 3: Пароль приглашения

**Decision**: Опциональный пароль на invite; хранение bcrypt hash; ввод через aiogram FSM после `/start`

**Rationale**: Защита от утечки ссылки. FSM — стандартный паттерн aiogram 3 для многошагового диалога. bcrypt — уже де-факто стандарт, лёгкая зависимость.

**Alternatives considered**:
- Пароль в URL (`?start=invite_TOKEN_PASS`) — виден в логах Telegram/браузера
- Без пароля всегда — проще, но риск при публичной рассылке
- TOTP / 2FA — overkill для 10–30 сотрудников

---

## Decision 4: Генерация токенов

**Decision**: `secrets.token_urlsafe(12)` с префиксом `invite_` в deep link payload

**Rationale**: Криптостойкость из stdlib, без внешних зависимостей. 12 байт ≈ 16 символов base64url — достаточно для ≤20 активных invite.

**Alternatives considered**:
- UUID4 — длиннее, избыточно
- Последовательные ID — предсказуемы

---

## Decision 5: Уведомления админу

**Decision**: Опциональный `ADMIN_NOTIFY_CHAT_ID` (Telegram group/supergroup); fallback — личные сообщения всем `ADMIN_USER_IDS`

**Rationale**: «Пишет в команду» из требования = корпоративная группа HR/IT. Бот должен быть добавлен в группу. Если группа не настроена — не теряем уведомления.

**Alternatives considered**:
- Email — нет инфраструктуры
- Webhook в Slack — вне scope v2
- Только `/users` без push — админ не узнает о новых без опроса

---

## Decision 6: Интерфейс админа

**Decision**: Команды бота (`/invite`, `/users`, `/user`) — без веб-UI

**Rationale**: Соответствует gate Simplicity из 001. Админ уже в Telegram. 5–7 команд покрывают все сценарии.

**Alternatives considered**:
- Mini App (Telegram Web App) — красивее, но +frontend
- Admin CLI только — неудобно с телефона

---

## Decision 7: Лимиты и защита от брутфорса пароля

**Decision**: ≤3 неверных попыток пароля за 15 минут на пару (user_id, invite_id); затем блокировка попыток для этого invite

**Rationale**: Invite-пароли обычно простые (корпоративные коды); rate limit снижает риск перебора.

**Alternatives considered**:
- Без лимита — риск при коротком пароле
- CAPTCHA — нет в Bot API

---

## Decision 8: Параметры invite по умолчанию

**Decision**: `expires_at` = +7 дней; `max_uses` = 1; оба настраиваются при создании

**Rationale**: Одноразовые ссылки для персонального приглашения; многоразовые (`max_uses=0` или N) — для рассылки в командный чат.

**Alternatives considered**:
- Бессрочные по умолчанию — риск утечки
- Только одноразовые — неудобно для «ссылка для всего отдела»

---

## Resolved clarifications

| Topic | Resolution |
|---|---|
| Как админ «кидает ссылку» | Копирует из ответа бота в любой мессенджер |
| Как видеть пользователей | `/users` и `/user <id>` в боте |
| Bootstrap админов | По-прежнему `ADMIN_USER_IDS` в env |
| Username для ссылки | `BOT_USERNAME` env или `getMe` при старте |
| Отзыв доступа | `/user block` + `/invite revoke` |
