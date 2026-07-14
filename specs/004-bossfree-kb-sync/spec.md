# Feature Specification: Синхронизация базы знаний Boss Free в локальный RAG

**Feature Branch**: `004-bossfree-kb-sync`

**Created**: 2026-07-14

**Status**: Draft

**Depends on**: `001-company-telegram-bot` (knowledge/, KnowledgeIndexer, Chroma, Q&A в Telegram)

**Input**: У компании TOPIX есть база знаний на Boss Free (`https://topix.bossfree.pro/`). Нужно, чтобы корпоративный Telegram-бот отвечал по этим статьям через существующий RAG. Выбранный подход MVP: периодическая/ручная выгрузка статей в Markdown-файлы → существующий `reindex` (без live-запросов к Boss Free на каждый вопрос Telegram и без `/sync_kb`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Оператор выгружает статьи Boss Free (Priority: P1)

Оператор/разработчик запускает CLI-команду синхронизации с учётными данными Boss Free из `.env`. Система скачивает доступные статьи, конвертирует HTML → Markdown и сохраняет в `knowledge/bossfree/`.

**Why this priority**: Без локальных файлов RAG бота не из чего индексировать.

**Independent Test**: При валидных credentials `python -m src.cli knowledge sync-bossfree` создаёт ≥1 `.md` файл с текстом статьи и выводит JSON-сводку (сколько скачано/пропущено/ошибок).

**Acceptance Scenarios**:

1. **Given** в `.env` заданы `BOSSFREE_EMAIL` и `BOSSFREE_PASSWORD`, **When** запускается sync, **Then** для каждой доступной статьи появляется Markdown-файл под `knowledge/bossfree/` с заголовком и текстом (HTML очищен).
2. **Given** статья уже выгружена и `updated_at` не изменился, **When** повторный sync без `--force`, **Then** файл не перезаписывается без необходимости (идемпотентность / skip unchanged).
3. **Given** credentials неверны или API недоступен, **When** sync, **Then** команда завершается с ненулевым кодом и понятной ошибкой в stderr/JSON, без повреждения уже существующих файлов.

---

### User Story 2 - Индексация и ответ бота по статьям (Priority: P1)

После sync оператор запускает существующий `knowledge reindex`. Сотрудник в Telegram задаёт вопрос по содержимому выгруженных статей и получает ответ со ссылкой на источник (title документа).

**Why this priority**: Это ценность для конечного пользователя — ответ по реальной БЗ компании.

**Independent Test**: Sync демо-статьи про отпуск → reindex → вопрос «как взять отпуск» → бот отвечает с citation на соответствующий MD title.

**Acceptance Scenarios**:

1. **Given** sync + reindex выполнены, **When** сотрудник спрашивает по теме, покрытой статьёй Boss Free, **Then** ответ строится на чанках из `knowledge/bossfree/` и в источниках есть title статьи.
2. **Given** статья была обновлена в Boss Free и повторно синхронизирована, **When** reindex, **Then** индекс отражает новый текст (старые чанки документа заменяются).

---

### User Story 3 - Пустые и медиа-only статьи (Priority: P2)

Часть статей в Boss Free пустые или почти без текста (только картинки/видео). Sync не падает: такие статьи либо пропускаются с записью в отчёт, либо сохраняются с пометкой, что текста нет.

**Why this priority**: В выгрузке ~14 коротких/пустых статей; без явной политики sync выглядит «сломанным».

**Independent Test**: Mock статья с пустым `content` → sync → в summary `skipped_empty ≥ 1`, остальные статьи сохранены.

**Acceptance Scenarios**:

1. **Given** статья с пустым/почти пустым текстом после очистки HTML, **When** sync, **Then** она не ломает весь прогон; учитывается в отчёте как skipped/empty.
2. **Given** статья с картинками и текстом, **When** sync, **Then** текст сохраняется; URL картинок могут остаться как markdown-links/alt (OCR картинок вне MVP).

---

### Edge Cases

- Что если slug или title содержит символы, недопустимые в имени файла?
- Что если статья удалена в Boss Free, а локальный файл остался?
- Что если часть статей отдаёт 404/403 при fetch по slug?
- Что если токен сессии истекает mid-sync (много статей)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Система MUST аутентифицироваться в Boss Free API (`POST /api/login`) с credentials из env.
- **FR-002**: Система MUST получать список категорий и статей, доступных сервисному аккаунту (`GET /api/common/category`, `GET /api/common/posts`).
- **FR-003**: Система MUST загружать полный HTML статьи по slug (`GET /api/common/posts/{slug}`).
- **FR-004**: Система MUST конвертировать HTML статьи в Markdown (заголовок + текст) и сохранять под `knowledge/bossfree/` с понятной структурой каталогов (по категории или slug).
- **FR-005**: Система MUST включать в файл метаданные источника: Boss Free `id`, `slug`, `updated_at`, URL вида `https://topix.bossfree.pro/post/{slug}` (frontmatter или префикс).
- **FR-006**: Система MUST предоставлять CLI: `python -m src.cli knowledge sync-bossfree` с опцией `--force` и JSON-сводкой результата.
- **FR-007**: После sync существующий `knowledge reindex` MUST индексировать новые/изменённые `.md` без изменения контракта RAG для Telegram.
- **FR-008**: Credentials MUST храниться только в env (`.env` / секреты деплоя), не в репозитории и не в выгруженных Markdown.
- **FR-009**: Пустые статьи MUST не ронять весь sync; результат MUST отражать skipped/errors.
- **FR-010**: MVP MUST NOT ходить в Boss Free при каждом вопросе пользователя Telegram; MUST NOT добавлять `/sync_kb` (отложено).

### Key Entities

- **BossFreeArticle**: статья из API (`id`, `title`, `slug`, `category_id`, `content` HTML, `updated_at`)
- **BossFreeCategory**: узел дерева категорий (`id`, `title`, `parent_id`, children)
- **SyncedDocument**: локальный Markdown-файл + метаданные sync (hash/updated_at для skip)
- **SyncReport**: итог прогона (fetched, written, skipped, errors)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Один прогон sync выгружает ≥90% доступных непустых статей в Markdown без ручного копирования.
- **SC-002**: После sync + reindex вопрос по выгруженной теме получает ответ с релевантным источником в течение обычного SLA бота (как в 001).
- **SC-003**: Повторный sync без изменений завершается быстрее полного rewrite и не портит уже выгруженные файлы при сетевой ошибке mid-run (per-article write).
- **SC-004**: Credentials не появляются в git; `.env.example` документирует только имена переменных.

## Assumptions

- Используется существующий сервисный аккаунт с ролью «Пользователь» (чтение статей по должности); админ-API/export не требуется для MVP.
- Домен tenant: `topix` → API base `https://topix.bossfree.pro/api`.
- OCR скриншотов и транскрипция видео — out of scope MVP.
- Live search Boss Free и Telegram-команда sync — out of scope MVP (можно добавить позже).
- Демо-документы в `knowledge/` могут остаться рядом; sync пишет в подкаталог `knowledge/bossfree/`.
- Обновление изменённых статей в продакшене — ручной запуск CLI (cron позже, не блокер MVP).
