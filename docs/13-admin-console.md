# Admin Console (Web UI) — управление `/v1/admin/*`

Цель: добавить **веб‑админку** (в `apps/web`) для управления всеми существующими admin API эндпоинтами FastAPI (`/v1/admin/*`) через интерфейс, не ломая основной UI (Top‑10 deals).

> Важно: текущие admin endpoints **не защищены**. Для production админка должна работать только при наличии админ‑токена и/или сетевых ограничений.

---

## 1) Scope: какие методы есть сейчас

Текущий backend admin API (prefix: `/v1/admin`):

### Ingestion
- `POST /v1/admin/ingest`
  - body: `{ sku_key, country_code, min_confidence, skip_low_confidence, update_existing }`
  - назначение: ручной запуск ingestion для конкретного Golden SKU и страны (пишет в `offers` + всегда upsert в `raw_offers`)
- `GET /v1/admin/ingest/countries`
  - назначение: список поддерживаемых стран для ingestion

### Reconcile (raw_offers → offers)
- `POST /v1/admin/reconcile`
  - body: `{ limit, dry_run, country_code? }`
  - назначение: промоут raw_offers → offers, возвращает stats + debug samples + llm_* метрики

### Explain/debug raw_offers
- `GET /v1/admin/raw-offers/{raw_offer_ref}?include_candidates=false|true`
  - назначение: объяснить детерминированный парсинг/матчинг/статус LLM для конкретного raw_offer (по `id` или `raw_offer_id`)

### Golden SKUs
- `GET /v1/admin/skus?limit=...`
- `GET /v1/admin/skus/{sku_key}`
- `POST /v1/admin/skus`

### Debug endpoints
- `GET /v1/admin/debug/serpapi?limit=...`
- `GET /v1/admin/debug/serpapi/{filename}`
- `GET /v1/admin/debug/fx`
- `GET /v1/admin/debug/llm`

---

## 2) Принципы UI (учёт текущего frontend)

Текущий UI (home/leaderboard) — это “product UI”. Admin UI должен быть:
- **отдельным маршрутом**: `/admin` (и вложенными `/admin/...`)
- визуально совместимым (Tailwind + shadcn/ui), но без “heavy” анимаций
- с упором на:
  - быстрый запуск операций
  - прозрачные stats и debug
  - copy‑friendly JSON (встроенный viewer)
  - безопасное обращение к админ‑API (auth)

Рекомендуемые shadcn компоненты:
- `tabs`, `card`, `button`, `badge`, `dialog`, `scroll-area`, `separator`, `accordion`, `tooltip`
- JSON viewer: простой компонент на базе `ScrollArea` + `pre` + copy button

---

## 3) Структура Admin Console (экраны)

### 3.1 Dashboard (оперативная панель)
**Цель**: “что сейчас происходит” без запуска операций.
- Health: `GET /health`
- Config snapshot:
  - `GET /v1/admin/debug/llm` (enabled/key_set/model/budget)
  - `GET /v1/admin/debug/fx` (ok/rates_count/eur)
- SerpAPI debug files: `GET /v1/admin/debug/serpapi?limit=...` (ссылки на просмотр)
- (опционально) вывести суточные метрики SerpAPI из Redis, если добавим endpoint `GET /v1/admin/metrics` (см. TODO)

UI:
- cards в 2 колонки (desktop), 1 колонка (mobile)
- “Copy JSON” на каждой карточке

### 3.2 Ingestion
Форма + вывод результатов:
- поля:
  - `sku_key` (dropdown из `/v1/admin/skus` + возможность ручного ввода)
  - `country_code` (dropdown из `/v1/admin/ingest/countries`)
  - `min_confidence` (high/medium/low)
  - `skip_low_confidence` (toggle)
  - `update_existing` (toggle)
- кнопка “Run ingestion”
- после ответа показать stats таблицей + JSON raw response

UX:
- блок “Preview query”: показывать, что ingestion использует query вида `"iPhone ... <STORAGE>"` (как подсказка)
- предупреждение, что ingestion пишет в `offers` (в отличие от daily refresh, который raw-only)

### 3.3 Reconcile
Форма:
- `limit` (1..5000)
- `dry_run` (по умолчанию true)
- `country_code` (optional)

Вывод:
- stats (включая llm_* поля) в таблице
- debug: `created_offer_ids`, `matched_raw_offer_ids`, `sample_reason_codes`
- кнопка “Run again (same params)”

UX:
- если `dry_run=false`, показать confirm dialog (в проде)
- добавить polling (если мы позже сделаем async jobs) — пока не нужно

### 3.4 Raw Offer Explain
Поля:
- `raw_offer_ref` (строка: numeric id или uuid raw_offer_id)
- `include_candidates` checkbox

Вывод (аккордеоном):
- `rawOffer` (основные поля)
- `deterministic` (attrs/confidence/flags)
- `catalog` (exists/matched/candidates counts)
- `llm` (attempted/chosen/confidence/would_call_now)
- `debug` (snapshots)

### 3.6 Patterns (Contract + Condition) + LLM Suggestions
Цель: быстро расширять детекторы **без деплоя**:
- contract/plan (подписка/рассрочка) → исключаем из promotion
- condition hints (new/used/refurbished) → аналитика и fallback

Backend:
- CRUD:
  - `GET /v1/admin/patterns`
  - `POST /v1/admin/patterns`
  - `DELETE /v1/admin/patterns/{pattern_id}` (soft-disable)
- LLM recommendations:
  - `POST /v1/admin/patterns/suggest` — читает последние ~2000 `raw_offers` (title + product_link), батчит и возвращает список фраз + match_count + примеры.

UI:
- Таблица текущих фраз (kind/phrase/enabled/source) + add/remove
- Кнопка “Suggest via LLM” + просмотр рекомендаций + кнопки “Add” для выбранных фраз

### 3.5 Golden SKUs
Вкладки:
- List: таблица (sku_key, model, storage, color, display_name)
- Create:
  - form (model/storage/color/condition + optional variants)
  - submit → `POST /v1/admin/skus`
  - show created sku_key
- View:
  - quick lookup by sku_key → `GET /v1/admin/skus/{sku_key}`

---

## 4) Auth / Security (обязательно для production)

Минимально:
- env: `ADMIN_TOKEN`
- backend: требовать header `X-Admin-Token: <token>` на всех `/v1/admin/*` (кроме, возможно, `/health`)
- frontend: на `/admin` — простая форма “Admin token”, хранить в памяти/`sessionStorage` (не в localStorage), добавлять header ко всем запросам

Рекомендуемо дополнительно:
- Railway: ограничить доступ к админке по IP (если возможно) или вынести admin UI в отдельный protected deployment
- Логи: **не логировать** токены/секреты

---

## 5) Railway deployment notes (cron + admin)

- Admin UI (Next.js) должен обращаться к `NEXT_PUBLIC_API_URL` (как и product UI).
- Cron job (daily refresh) запускается на Railway как отдельная команда внутри сервиса `services/api`:
  - `python -m scripts.refresh_daily`
- Для админки важно различать:
  - manual ingestion (пишет `offers`)
  - daily refresh (raw-only → reconcile)

