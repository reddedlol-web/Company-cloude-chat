# Пилот: AutoClaw / OpenClaw (вариант 2)

Пошаговая инструкция для корпоративного Telegram-бота с базой знаний.  
Срок пилота: **1–2 недели**, 5 тестеров, 20–30 документов.

См. также: [implementation-options.md](./implementation-options.md) — зачем этот вариант и бюджет.

---

## Коротко: что мы делаем

**Telegram-бот**, который отвечает **только по документам компании** из папки `knowledge/`. Сервер и OpenClaw — через **AutoClaw** (облако) или **свой VPS** с OpenClaw CLI. API-модель — **ваш ключ** (OpenRouter / OpenAI).

```
Сотрудник → Telegram → OpenClaw → папка knowledge/ → LLM → ответ + источник
```

---

## Что уже лежит в репозитории

```
openclaw/
├── openclaw.json.example   # шаблон конфига (Telegram, доступ, модель)
├── .env.example            # токены (не коммитить!)
├── pilot-testers.md        # таблица Telegram ID тестеров
└── workspace/
    ├── SOUL.md             # «характер» бота — правила для компании
    ├── AGENTS.md           # как искать ответы
    └── knowledge/          # база знаний (есть демо-документы)
        ├── faq/
        ├── policies/
        └── onboarding/
```

Демо-документы — **выдуманная компания** (`company.example`). Замени их на реальные регламенты заказчика перед пилотом.

---

## Шаг 0. Уточнить у заказчика (5 минут)

Из [implementation-options.md](./implementation-options.md#вопросы-заказчику-уточнить-перед-стартом):

- Сколько человек в пилоте (цель: **5**).
- Можно ли слать текст документов в **облачный API** (OpenRouter/OpenAI).
- Telegram **группа** или личные сообщения боту.
- Кто обновляет базу при смене регламентов.

---

## Шаг 1. Telegram-бот (15 мин)

1. В Telegram открой **@BotFather**.
2. Команда `/newbot` → имя и username (например `Company KB Bot`, `@company_kb_bot`).
3. Сохрани **токен** — он пойдёт в `.env` как `TELEGRAM_BOT_TOKEN`.
4. В BotFather: `/setprivacy` → **Disable** (если бот в **группе** и должен видеть все сообщения; для режима «только @упоминание» можно оставить Enable).
5. Создай **тестовую группу**, добавь бота, добавь 5 тестеров.

---

## Шаг 2. API-ключ LLM (10 мин)

Рекомендация для пилота: [OpenRouter](https://openrouter.ai/keys) + недорогая модель (в шаблоне: `google/gemini-2.0-flash-001`).

1. Зарегистрируйся, пополни баланс ($10–20 на пилот).
2. Создай ключ → `OPENROUTER_API_KEY` в `.env`.

AutoClaw **не оплачивает** AI — только хостинг. Счёт за запросы идёт на ваш ключ.

---

## Шаг 3A. Деплой через AutoClaw (быстрый путь)

1. Открой [autoclaw.dev](https://autoclaw.dev) → документация / Deploy.
2. Создай инстанс OpenClaw (managed).
3. В dashboard задай переменные из `openclaw/.env.example`.
4. Загрузи **workspace**:
   - `SOUL.md`, `AGENTS.md`
   - всю папку `knowledge/` (сначала замени демо на документы заказчика).
5. Вставь конфиг Telegram из `openclaw.json.example`:
   - `allowFrom` — Telegram ID тестеров (см. `pilot-testers.md`).
   - `groups` — ID группы (отрицательное `-100...`), если бот в группе.
6. Запусти gateway / перезапусти инстанс.

Официальная документация Telegram-канала: [docs.openclaw.ai/channels/telegram](https://docs.openclaw.ai/channels/telegram).

---

## Шаг 3B. Свой сервер / локально (альтернатива AutoClaw)

Требования: Node.js 22+, macOS/Linux.

```bash
# Установка CLI
npm install -g openclaw@latest

# Из корня репозитория
chmod +x scripts/sync-to-openclaw.sh
./scripts/sync-to-openclaw.sh

# Заполни ~/.openclaw/.env и allowFrom в ~/.openclaw/openclaw.json
openclaw doctor          # проверка конфига
openclaw gateway         # запуск бота
```

Первый DM: если `dmPolicy: "pairing"`, одобри код:

```bash
openclaw pairing list telegram
openclaw pairing approve telegram <CODE>
```

В нашем шаблоне стоит `allowlist` — тогда сразу пропиши numeric ID в `allowFrom`.

---

## Шаг 4. База знаний (1–2 дня)

1. Собери **20–30** актуальных документов заказчика (md/pdf).
2. Разложи по `knowledge/faq/`, `policies/`, `onboarding/`.
3. Удали или замени демо-файлы из репозитория.
4. Синхронизируй на сервер (`sync-to-openclaw.sh` или upload в AutoClaw).
5. Перезапусти gateway / reindex при необходимости.

Правила для бота уже в `SOUL.md` — отвечать только из `knowledge/`, указывать источник, не выдумывать.

---

## Шаг 5. Доступ только для своих (важно)

В `openclaw.json.example`:

| Поле | Зачем |
|------|--------|
| `allowFrom` | Кто может писать боту в личку |
| `groups."-100..."` | Разрешённая корпоративная группа |
| `groups.*.allowFrom` | Кто в группе может вызывать бота |
| `requireMention: true` | Бот отвечает только на `@bot` в группе |

Заполни `openclaw/pilot-testers.md`, перенеси ID в конфиг.

**Частая ошибка:** ID группы (`-100...`) кладут в `groupAllowFrom` — так нельзя. Группа → `groups`, люди → `allowFrom` / `groupAllowFrom`.

---

## Шаг 6. Тест пилота (3–5 дней)

Дай тестерам список вопросов, на которые **точно есть** ответ в базе:

| Вопрос | Ожидаемый источник (демо) |
|--------|---------------------------|
| Как оформить удалёнку? | `policies/remote-work.md` |
| Сколько дней отпуска? | `policies/leave-policy.md` |
| Сломался ноутбук — куда? | `faq/it-support.md` |
| Что в первый день? | `onboarding/first-day.md` |
| Вопрос вне базы («курс доллара») | «В базе нет информации» |

Фиксируй: неверные ответы, галлюцинации, медленные ответы, стоимость API (AutoClaw dashboard / OpenRouter usage).

---

## Шаг 7. Критерии «пилот удался»

- ≥ **80%** тестовых вопросов — правильный ответ с указанием источника.
- Тестеры понимают, **когда** боту можно доверять.
- Бюджет API укладывается в **$50–120/мес** при текущей нагрузке (см. implementation-options).
- Заказчик согласен обновлять `knowledge/` при смене регламентов.

Если да → планируем **вариант 1** (свой бот + API) для продакшена. Если нет → дорабатываем базу / промпты или меняем модель.

---

## Бюджет пилота (ориентир)

| Статья | Цена |
|--------|------|
| AutoClaw / VPS | $5–50/мес |
| OpenRouter API | $10–30 на 2 недели пилота |
| **Итого** | **~$50–80** на период пилота |

---

## Troubleshooting

| Проблема | Что проверить |
|----------|----------------|
| Бот молчит | `openclaw gateway` запущен? токен в `.env`? |
| «Unauthorized» | Telegram ID в `allowFrom`? |
| В группе не отвечает | `requireMention` — нужен `@bot`; privacy mode в BotFather |
| Выдумывает факты | усилить `SOUL.md`; проверить, что файл реально в `knowledge/` |
| Дорого | сменить модель на более дешёвую в `agent.model` |

Логи: `openclaw logs --follow`  
Проверка конфига: `openclaw doctor`

---

## Следующий шаг после пилота

Перенос на **свой Telegram-бот + RAG + API** (вариант 1 в том же репозитории) — те же документы, тот же Telegram, но полный контроль и админка.
