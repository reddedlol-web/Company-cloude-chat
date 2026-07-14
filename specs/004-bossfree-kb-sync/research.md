# Research: Синхронизация Boss Free → локальный RAG

**Feature**: `004-bossfree-kb-sync`  
**Date**: 2026-07-14

## Decision 1: Sync to files, not live API per question

**Decision**: Выгружать статьи в `knowledge/bossfree/*.md` и использовать существующий Chroma RAG. Не вызывать Boss Free при каждом сообщении в Telegram.

**Rationale**: Встроенный search Boss Free слабый (запрос «1С» → 0). Локальный embeddings-поиск уже есть и работает. Sync даёт офлайн, повторяемость и простой дебаг файлов. Latency и зависимость от их API в hot path избыточны для ≤50 пользователей.

**Alternatives considered**:
- Live `POST /common/search` + fetch top N — плохой поиск, auth на каждый запрос, хрупкость
- Гибрид sync + `/sync_kb` — полезно позже, out of scope MVP по выбору заказчика
- Парсинг HTML UI (scraping) — хрупче REST API, который уже есть

---

## Decision 2: Неофициальный REST API Boss Free

**Decision**: Использовать reverse-engineered, но стабильные эндпоинты SPA:

| Step | Method | Path | Notes |
|---|---|---|---|
| Login | POST | `/api/login` | body `{login, password}` → `accessToken` + `refreshToken` |
| Auth | header | `Authorization: Bearer <accessToken>` | + Cookie `refreshToken` / `accessToken` (иначе 401) |
| Categories | GET | `/api/common/category` | дерево |
| Posts list | GET | `/api/common/posts` | id, title, slug, category_id |
| Post full | GET | `/api/common/posts/{slug}` | `content` = HTML |
| Base URL | | `https://{tenant}.bossfree.pro/api` | tenant=`topix` |

**Rationale**: Публичного documented API нет; эндпоинты подтверждены login + выгрузкой 74 статей. Админ `GET /admin/posts/export/{id}` даёт 403 для роли «Пользователь» — не нужен.

**Alternatives considered**:
- Админ export blob — нужны права админа
- Ручной copy-paste — не масштабируется
- Запрос официального API у вендора — не блокер MVP

**Risk**: Breaking change у вендора. Mitigation: контракт в `contracts/cli.md` + mock fixtures из сниппетов ответов; при поломке — быстрый фикс client.

---

## Decision 3: HTML → Markdown library

**Decision**: Предпочтительно `markdownify` (или thin wrapper над BeautifulSoup) для `content` HTML → Markdown body. Заголовок = `title` статьи отдельной `#` строкой / frontmatter.

**Rationale**: Статьи содержат `<p>`, списки, ссылки, `<img>`, иногда iframe/video. Нужен предсказуемый plain text для chunker. stdlib-only strip_tags потеряет структуру списков.

**Alternatives considered**:
- Только `html2text` — тоже ок, схожий результат
- Сырой HTML в файл — хуже для RecursiveCharacterTextSplitter и источников
- OCR картинок (Vision API) — дорого, out of MVP

**Images/video MVP**: сохранять как markdown image/link с URL; не скачивать медиа в `knowledge/` в MVP (текст важнее для RAG).

---

## Decision 4: File layout and naming

**Decision**:

```text
knowledge/bossfree/
  <top-category-slug>/
    <subcategory-slug>/
      <post-slug>.md
```

Frontmatter:

```yaml
---
bossfree_id: 12191
slug: otpusk-otgul-za-svoy-schet
updated_at: "2024-..."
source_url: https://topix.bossfree.pro/post/otpusk-otgul-za-svoy-schet
category_path: "Компания / Политики / Отпуска"
---
```

**Rationale**: Категории совпадают с UX Boss Free; indexer уже берёт `path.stem` как title — для citation лучше override: первая строка `# Title` из статьи (indexer uses stem сегодня → в research зафиксировать: либо улучшить indexer title из H1/frontmatter в follow-up, либо писать filename из human title с sanitize). **MVP pragmatic**: filename = `slug.md`, внутри файла `# {title}` — citation сейчас из stem=slug (не идеально). Prefer small indexer enhancement: title from first `# ` heading if present — optional task; иначе frontmatter ignore и `# Title` + slug filename acceptable for MVP if we teach citation via chunk metadata later.

**Практичное MVP-решение**: писать `# {title}` первой строкой body; расширить indexer: если текст начинается с `# `, брать эту строку как `title` вместо `path.stem`. Минимальный diff, лучшие citations.

**Alternatives considered**:
- Плоский каталог только по slug — потеря иерархии
- Один огромный MD — плохой chunking / updates
- Хранить сырой JSON dump — неудобно для ручного ревью

**Deleted posts**: MVP не удаляет локальные файлы автоматически (безопаснее). Опциональный `--prune` — later.

---

## Decision 5: Skip / incremental strategy

**Decision**: При sync сравнивать `updated_at` (и/или hash HTML) из API с frontmatter локального файла; skip если совпало. `--force` перезаписывает всё.

**Rationale**: 74 статьи × full download каждый раз приемлемо, но skip ускоряет и снижает нагрузку на их API.

**Alternatives considered**:
- Всегда rewrite — проще, но шумнее в git/mtime
- ETag — API не отдаёт явно для list

---

## Decision 6: Git tracking of generated knowledge

**Decision**: Рекомендовать **коммитить выгруженные MD** в private repo (или в data volume на сервере) — контент корпоративный, нужен reproducible deploy без обязательного sync на старте контейнера. `.env` с паролем — никогда не коммитить.

**Rationale**: Деплой бота уже ожидает файлы в `knowledge/`. Sync на проде — ручной шаг после обновления БЗ.

**Alternatives considered**:
- Always gitignore + sync at container start — нужен секрет + сеть при деплое
- Только на сервере volume — ок для prod, хуже для локальной разработки

---

## Decision 7: Empty articles

**Decision**: После HTML→text, если `len(stripped) < 50` — `skipped_empty`, файл не писать (или писать stub только с `--keep-empty`, default off).

**Rationale**: В выгрузке ~14 почти пустых статей; пустые документы ломают indexer (`Document is empty`).

---

## Decision 8: HTTP client

**Decision**: `httpx` (sync client в CLI async-обёртке или sync в thread) с явными timeout; хранить cookies session после login.

**Rationale**: Уже распространён в Python-проектах; удобные cookies. stdlib urllib работает (подтверждено), но httpx читаемее для retry.

**Auth caveat**: Bearer без cookie `refreshToken`/`accessToken` → 401. Client MUST set both.

---

## Resolved unknowns

| Former unknown | Resolution |
|---|---|
| Format of external «DB» | Boss Free SPA + REST JSON, HTML `content` |
| Official API? | No; use common/* endpoints |
| Admin export? | Forbidden for user role; not needed |
| Live vs sync | Sync (variant 1) |
| OCR | Out of MVP |
| `/sync_kb` | Deferred |
