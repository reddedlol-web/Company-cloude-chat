# Contract: Telegram Bot Commands

**Feature**: `001-company-telegram-bot`  
**Version**: 1.0.0

## Message handling

### Text message (default)

**Trigger**: Any text message that is not a command.

**Preconditions**:
- Sender `telegram_user_id` ∈ `ALLOWED_USER_IDS`
- Sender has not exceeded daily limit

**Flow**:
1. Validate access → rate limit check
2. RAG retrieval (top-K chunks)
3. LLM generation with system prompt
4. Reply with answer + sources

**Success response** (Telegram message):
```text
{answer_text}

📎 Источники: {source1}, {source2}
```

**Error responses**:

| Condition | Message |
|---|---|
| Unauthorized | `⛔ У вас нет доступа к этому боту.` |
| Rate limited | `⏳ Дневной лимит ({limit}) исчерпан. Попробуйте завтра.` |
| No answer in KB | `❓ В базе знаний нет информации по вашему вопросу.` |
| API error | `⚠️ Сервис временно недоступен. Попробуйте позже.` |
| Message too long | `✂️ Сократите вопрос до 2000 символов.` |

---

## Commands

### `/start`

**Access**: All users (including unauthorized — shows access denied for non-whitelisted).

**Response (authorized)**:
```text
👋 Привет! Я корпоративный помощник.
Задайте вопрос по регламентам и документам компании.
Лимит: {remaining}/{limit} вопросов сегодня.
```

**Response (unauthorized)**:
```text
⛔ У вас нет доступа. Обратитесь к администратору.
```

---

### `/help`

**Access**: Authorized users only.

**Response**:
```text
📖 Как пользоваться:
• Напишите вопрос обычным текстом
• Я отвечу на основе документов компании
• Если ответа нет в базе — скажу честно

Команды:
/start — начало
/help — эта справка
/limit — остаток лимита на сегодня
```

---

### `/limit`

**Access**: Authorized users only.

**Response**:
```text
📊 Использовано сегодня: {used}/{limit}
Осталось: {remaining}
Сброс: 00:00 UTC
```

---

### `/reindex` (admin only)

**Access**: Users in `ADMIN_USER_IDS` env var.

**Behavior**: Triggers full reindex of `knowledge/` directory.

**Response (success)**:
```text
✅ Индексация завершена.
Документов: {count}, чанков: {chunks}
```

**Response (in progress)**:
```text
⏳ Индексация запущена...
```

**Response (unauthorized)**:
```text
⛔ Команда доступна только администратору.
```

---

## System prompt contract (LLM)

```text
You are a corporate knowledge assistant. Answer ONLY based on the provided context.
If the context does not contain the answer, say "В предоставленных документах нет информации по этому вопросу."
Do not invent facts. Respond in the same language as the user's question.
Cite source document titles when answering.
```

**Context injection format**:
```text
Context:
---
[Source: {title}]
{chunk_text}
---
(repeat for each chunk)

User question: {question}
```
