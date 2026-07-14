# Contract: CLI — Boss Free knowledge sync

**Feature**: `004-bossfree-kb-sync`  
**Date**: 2026-07-14

## Command

```bash
python -m src.cli knowledge sync-bossfree [--force] [--dry-run]
```

### Options

| Flag | Default | Meaning |
|---|---|---|
| `--force` | false | Перезаписать все статьи, игнорируя `updated_at` |
| `--dry-run` | false | Сходить в API / посчитать, не писать файлы |

### Environment

| Var | Required | Default | Description |
|---|---|---|---|
| `BOSSFREE_EMAIL` | yes | — | login email |
| `BOSSFREE_PASSWORD` | yes | — | password |
| `BOSSFREE_BASE_URL` | no | `https://topix.bossfree.pro/api` | API root |
| `BOSSFREE_ORIGIN` | no | `https://topix.bossfree.pro` | для `source_url` |
| `KNOWLEDGE_DIR` | no | `./knowledge` | корень знаний (sync пишет в `{KNOWLEDGE_DIR}/bossfree`) |

### Exit codes

| Code | When |
|---|---|
| 0 | Login ok; процесс завершён; допустимы частичные `errors` если `written + skipped_* > 0` |
| 1 | Login failed / missing env / fatal config |
| 2 | Login ok, но **ни одна** статья не processed successfully и есть errors |

### stdout (JSON)

```json
{
  "status": "ok",
  "fetched": 74,
  "written": 60,
  "skipped_unchanged": 10,
  "skipped_empty": 4,
  "errors": [
    {"slug": "example", "message": "HTTP 404"}
  ],
  "knowledge_dir": "knowledge/bossfree"
}
```

Не печатать tokens, passwords, raw cookies.

### stderr

Человекочитаемые progress/warnings (optional); секреты не логировать.

## Upstream API contract (consumed)

Не наш сервер — фиксация ожиданий client:

### POST `/login`

Request:

```json
{"login": "<email>", "password": "<password>"}
```

Response 200:

```json
{
  "accessToken": "<jwt>",
  "refreshToken": "<jwt>",
  "user": {"id": 0, "access": "Пользователь"},
  "organizations": [{"domain": "topix", "name": "TOPIX GROUP"}]
}
```

Subsequent requests: `Authorization: Bearer <accessToken>` **and** Cookie containing `refreshToken` (and preferably `accessToken`).

### GET `/common/category` → `BossFreeCategory[]` (tree)

### GET `/common/posts` → list items `{id,title,slug,sort,category_id}`

### GET `/common/posts/{slug}` → full article with HTML `content`

## Follow-up (same feature pipeline)

После успешного sync оператор запускает существующий контракт:

```bash
python -m src.cli knowledge reindex [--force]
```

Этот контракт не меняется в 004; sync лишь наполняет файлы.
