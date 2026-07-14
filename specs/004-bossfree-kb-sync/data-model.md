# Data Model: Boss Free → local knowledge

**Feature**: `004-bossfree-kb-sync`  
**Date**: 2026-07-14

## Entities

### BossFreeCategory

Дерево разделов БЗ (read-only snapshot с API).

| Field | Type | Notes |
|---|---|---|
| id | int | PK из API |
| title | string | отображаемое имя |
| parent_id | int \| null | родитель |
| sort | int | порядок |
| children | list[BossFreeCategory] | вложенные `category` из API |

**Validation**: id > 0; title non-empty.

### BossFreeArticle (list item)

Краткая карточка из `GET /common/posts`.

| Field | Type | Notes |
|---|---|---|
| id | int | |
| title | string | |
| slug | string | уникальный путь статьи |
| category_id | int | |
| sort | int | optional |

### BossFreeArticleFull

Полная статья из `GET /common/posts/{slug}`.

| Field | Type | Notes |
|---|---|---|
| id | int | |
| title | string | |
| slug | string | |
| category_id | int | |
| content | string | HTML |
| updated_at | string | ISO/API timestamp |
| status | any | opaque |
| category | list[{id,title,parent_id}] | хлебные крошки |
| public | any | opaque |

**Derived**:
- `text_markdown` — результат HTML→MD
- `text_plain_len` — длина без разметки для empty check
- `source_url` = `{origin}/post/{slug}`
- `category_path` = `" / ".join(titles)` из `category` breadcrumbs

### SyncedDocument

Локальный файл Markdown.

| Field | Type | Notes |
|---|---|---|
| relative_path | string | от `knowledge/bossfree/` |
| bossfree_id | int | frontmatter |
| slug | string | frontmatter |
| updated_at | string | frontmatter; для skip |
| source_url | string | frontmatter |
| category_path | string | frontmatter |
| body | string | `# title` + markdown content |

**Validation**:
- filename = sanitized `slug` + `.md`
- path segments = sanitized category titles или id-slugs
- no credentials in file

### SyncReport

Итог CLI.

| Field | Type | Notes |
|---|---|---|
| status | `ok` \| `error` | `ok` если полный провал не случился; частичные ошибки допустимы |
| fetched | int | статей успешно скачано |
| written | int | файлов записано |
| skipped_unchanged | int | |
| skipped_empty | int | |
| errors | list[{slug\|id, message}] | |
| knowledge_dir | string | абсолютный/относительный путь |

## Relationships

```text
BossFreeCategory 1─* BossFreeArticle (category_id)
BossFreeArticle 1─1 BossFreeArticleFull (by slug)
BossFreeArticleFull 1─0..1 SyncedDocument (после успешной записи)
SyncRun produces SyncReport
```

## State transitions

### Sync document lifecycle

```text
[absent] --write--> [present]
[present] --unchanged skip--> [present]
[present] --force or updated_at changed--> [present updated]
[present] --remote deleted--> [present] (MVP: no auto-delete)
```

### Article processing

```text
listed → fetch(slug) → convert → empty? → skipped_empty
                              └→ write md → written
         └→ error → errors[]
```

## Storage notes

- Нет новых SQLite-таблиц в MVP (достаточно frontmatter + files).
- Существующая таблица `documents` обновляется только через `reindex` после sync.
- Опциональный later: таблица `bossfree_sync_state` — не требуется для MVP.
