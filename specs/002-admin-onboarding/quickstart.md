# Quickstart: Проверка админ-онбординга

**Feature**: `002-admin-onboarding`  
**Prerequisites**: Работающий бот из `001` (см. `specs/001-company-telegram-bot/quickstart.md`)

## 1. Конфигурация

Добавьте в `.env`:

```bash
# Существующие
ADMIN_USER_IDS=<ваш_telegram_id>
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...

# Новые для 002
BOT_USERNAME=YourCompanyBot          # без @
ADMIN_NOTIFY_CHAT_ID=-1001234567890  # опционально: ID группы HR/IT
INVITE_DEFAULT_DAYS=7
INVITE_DEFAULT_MAX_USES=1
```

Получить ID группы: добавьте бота в группу, напишите что-нибудь — смотрите логи или используйте @userinfobot.

## 2. Миграция БД

После реализации (Phase A):

```bash
python -m src.cli health   # проверка; миграция при старте бота
```

## 3. Сценарий: создать invite (админ)

1. Запустите бота: `python -m src.cli bot`
2. От аккаунта из `ADMIN_USER_IDS` отправьте:
   ```text
   /invite create label=Тест password=test123 days=1 uses=3
   ```
3. **Ожидание**: ответ со ссылкой `https://t.me/...?start=invite_...` и паролем

## 4. Сценарий: регистрация сотрудника

1. С другого Telegram-аккаунта (не в whitelist) откройте ссылку
2. Нажмите **Start**
3. Введите пароль `test123`
4. **Ожидание**: приветствие + возможность задать вопрос
5. **Ожидание**: уведомление в `ADMIN_NOTIFY_CHAT_ID` (если настроен)

## 5. Сценарий: список пользователей

```text
/users
```

**Ожидание**: новый пользователь в списке с username и датой регистрации.

## 6. Сценарий: блокировка

```text
/user block <telegram_id>
```

С заблокированного аккаунта отправьте вопрос.

**Ожидание**: `⛔ У вас нет доступа к этому боту.`

## 7. Сценарий: отзыв invite

```text
/invite revoke <token>
```

Новый пользователь по той же ссылке.

**Ожидание**: `❌ Приглашение недействительно...`

## 8. Автотесты

```bash
pytest tests/unit/test_invite.py -v
pytest tests/integration/test_onboarding_flow.py -v
```

## 9. Обратная совместимость

Пользователи из `ALLOWED_USER_IDS` без регистрации через invite должны работать как раньше — проверьте вопрос от env-whitelist аккаунта.

## Ссылки

- [Спецификация](./spec.md)
- [Модель данных](./data-model.md)
- [Контракт команд](./contracts/telegram-bot.md)
- [Базовый quickstart](../001-company-telegram-bot/quickstart.md)
