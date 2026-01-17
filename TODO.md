# Market Compass — План работ и ToDo

> Этот файл отслеживает текущий прогресс разработки. Задачи удаляются по мере выполнения.

---

## 🛠 Целевой стек технологий

### Frontend
| Технология | Назначение |
|------------|------------|
| **Next.js 16** ✅ | SSR/ISR, Edge Runtime для гео-логики |
| **Vercel** | Хостинг, Edge Functions, Analytics |
| **Tailwind CSS 4** ✅ | Стили |
| **shadcn/ui** ✅ | UI компоненты |
| **Zod** | Валидация API ответов |

### Backend
| Технология | Назначение |
|------------|------------|
| **FastAPI** (Python 3.11+) ✅ | REST API |
| **Docker** ✅ | Контейнеризация |
| **Railway** | Деплой, автоскейлинг |
| **Pydantic v2** ✅ | Схемы запросов/ответов |

### Данные и кеш
| Технология | Назначение |
|------------|------------|
| **PostgreSQL** (Neon / Supabase) | Основная БД |
| **Upstash Redis** | Кеш SerpAPI (TTL часы), курсы валют |
| **openexchangerates API** | Курсы валют (TTL ~1 час) |
| **Cloudflare CDN** | Кеширование ассетов, защита |

### Тестирование и обсервабилити
| Технология | Назначение |
|------------|------------|
| **GitHub Actions** | CI/CD |
| **Vitest** | Unit тесты |
| **Playwright** | E2E тесты |
| **Sentry** | Error tracking |
| **Checkly** | Мониторинг API/uptime |
| **Vercel Analytics** | Web analytics |

### LLM-слой
| Технология | Назначение |
|------------|------------|
| **GPT-5-mini** | Фолбэк-парсинг/мэтчинг Golden SKU (сложные случаи), извлечение сигналов trust, локализация контента |

---

## ✅ Завершённые этапы

### Phase 0.1 — Миграция фронтенда на Next.js ✅
- [x] Создан Next.js 16 проект с App Router в `apps/web`
- [x] Настроен Tailwind CSS 4 с кастомной темой iPassport
- [x] Настроен shadcn/ui (button, card, dialog, slider, etc.)
- [x] Перенесены все компоненты:
  - [x] Header, HeroSection, ModelSelector
  - [x] CompareCard, ComparisonModal
  - [x] Leaderboard, DealCard
  - [x] RiskSlider, TrustMeter, AnimatedNumber
  - [x] LocationModal
- [x] Добавлены "use client" директивы для клиентских компонентов
- [x] Проект собирается и запускается успешно

### Phase 0.2 — Инфраструктура бэкенда ✅
- [x] Создан FastAPI backend в `services/api`
- [x] Структура проекта:
  - [x] `app/main.py` — FastAPI instance, middleware, lifespan
  - [x] `app/settings.py` — Pydantic Settings
  - [x] `app/routes/ui.py` — GET /v1/ui/home
  - [x] `app/routes/redirect.py` — GET /r/offers/{offerId}
  - [x] `app/services/` — ranking, dedup, trust, hydration, serpapi_client
  - [x] `app/stores/` — postgres, redis
  - [x] `app/models/` — GoldenSku, Merchant, Offer
  - [x] `app/schemas/` — HomeResponse, Deal, etc.
- [x] Docker Compose для локальной разработки:
  - [x] FastAPI app
  - [x] PostgreSQL 16
  - [x] Redis 7
- [x] Dockerfile для FastAPI (multi-stage build)
- [x] Базовые тесты (health, home endpoint)

### Текущая структура:
```
apps/
├── web/               # ✅ Next.js 16 (основной фронтенд)
└── api/               # Node.js/Fastify прототип (deprecated, для референса)

services/
└── api/               # ✅ FastAPI backend (основной)
    ├── app/
    │   ├── main.py
    │   ├── settings.py
    │   ├── routes/
    │   ├── services/
    │   ├── stores/
    │   ├── models/
    │   └── schemas/
    ├── alembic/       # ✅ Database migrations
    │   └── versions/
    ├── tests/
    ├── Dockerfile
    └── pyproject.toml
```

---

## 🔄 Текущие задачи

### Phase 1 — Backend API (полная интеграция)

#### 1.1 База данных (PostgreSQL)
- [x] SQLAlchemy models:
  - [x] `golden_skus`
  - [x] `merchants`
  - [x] `offers`
- [x] Alembic миграции (async PostgreSQL support)
- [x] Seed данные: Golden SKU для iPhone 16 Pro/Max + sample offers

#### 1.2 Redis кеширование
- [x] Структура кеша (TTL политики)
- [x] Locks для hydration (предотвращение thundering herd)
- [x] Интеграция с Upstash Redis (production)
- [x] Унификация env: `CORS_ORIGINS` (+ совместимость с `ALLOWED_ORIGINS`), `SERPAPI_API_KEY` (+ `SERPAPI_KEY`), `AUTO_MIGRATE` в примерах
- [x] Подготовка к Upstash Redis (TLS CA certs в Docker + Redis ping/таймауты на старте)
- [x] Startup health-логи: явные `Postgres connected` / `Redis connected` в deploy output

#### 1.3 API эндпоинты
- [x] `GET /health`
- [x] `GET /v1/ui/home?sku=...&home=...&minTrust=...&lang=...`
- [x] `GET /r/offers/{offerId}` — redirect
- [x] API использует данные из PostgreSQL

#### 1.4 Курсы валют
- [x] Интеграция с openexchangerates API (FX service)
- [x] Кеширование в Redis (TTL ~1 час)
- [x] Добавлен FX сервис + Redis cache helpers (готово к подключению в ingestion/пересчёт price_usd)
- [x] Debug endpoint: `/v1/admin/debug/fx` для диагностики отсутствующих курсов (например EUR)

---

## Phase 2 — SerpAPI интеграция

- [x] SerpAPI клиент (структура для google_shopping + immersive)
- [x] Реальные вызовы SerpAPI (с кешированием в Redis, TTL 1-6h)
- [x] Fix: корректный выбор валюты для `extracted_price` (не использовать `alternative_price.currency`, если primary price в другой валюте)
- [x] Regex extraction для атрибутов iPhone (model/storage/color/condition)
- [ ] GPT-5-mini fallback для сложных случаев (low/medium confidence) **без ломки текущей архитектуры**
  - [x] `app/services/llm_parser.py`: deterministic-first, LLM as fallback; strict JSON validation
  - [x] Redis cache + lock для LLM: `llm:parse:{hash(...)}` + lock TTL 60s, cache TTL 180d
  - [x] Candidate-set matching: LLM выбирает SKU только из списка кандидатов из БД, возвращает `match_confidence` (0..1)
  - [x] Включение в проде через env (`LLM_ENABLED=true` + `OPENAI_API_KEY`) и мониторинг бюджета (calls/run)
  - [x] Persist минимальные артефакты: `match_confidence` + `match_reason_codes_json` / `trust_reason_codes_json` (offers)
  - [x] Budget policy (reconcile): cap LLM calls per run + expose metrics in `/v1/admin/reconcile` stats/logs
- [ ] Raw ingestion buffer (вариант A): сохранить все оплаченные результаты, даже если SKU ещё не существует
  - [x] Добавить таблицу `raw_offers` (Alembic migration) без обязательного `sku_id`
  - [x] Идемпотентность: unique key по `(source, country_code, source_product_id)` и fallback по hash(product_link)
  - [x] Писать туда все non-accessory результаты `google_shopping` (включая “не тот цвет/память”) — параллельно текущему ingestion
  - [x] Multi-variant detector (v1): если title перечисляет несколько storage → пометить `is_multi_variant=true`, **не вызывать LLM**, не промоутить в `offers`
  - [x] Contract/plan detector (v1): пометить `is_contract=true` (и исключить из leaderboard по продуктовой политике)
  - [x] Reconciliation job/service (v1, deterministic-only): промоутить `raw_offers` → `offers`, когда
    - появился соответствующий Golden SKU
    - улучшился deterministic/LLM парсер
    (без повторных SerpAPI запросов)
    - Реализация: `services/api/scripts/reconcile_raw_offers.py`
  - [ ] Словари для мультиязычности (минимальный набор): colors + accessory + contract + condition tokens (JP/DE/FR как старт)
    - [x] Базовые токены/паттерны для DE/FR/JP (colors/accessory/condition + contract flags)
    - [x] Добавлены базовые токены/паттерны для HK/AE/KR (colors/condition/accessory/contract)
    - [ ] Расширить словари под SG/AU/CA по мере появления реальных тайтлов
- [x] Trust Score (0-100) — базовый алгоритм
- [x] Ranking по effective price
- [x] Ingestion service: SerpAPI → extraction → FX → dedup → DB
- [x] Admin endpoint: `POST /v1/admin/ingest` для ручного тестирования
- [ ] Scheduled refresh jobs (worker)
- [ ] Scheduled refresh jobs (worker)
  - [x] Определили бюджет: 11 стран × Q=6 × daily → ~66 SerpAPI calls/day (cache-miss)
  - [ ] Cron job на Railway: `python -m scripts.refresh_daily` (raw-only ingest → reconcile)
  - [ ] Добавить/проверить метрики SerpAPI calls/day (Redis counters `metrics:serpapi:*:YYYYMMDD`)
- [ ] ⚠️ Удалить seed-данные и заменить реальными из SerpAPI
- [x] Admin endpoint: `POST /v1/admin/reconcile` (dry-run by default) + debug logs
- [x] Admin endpoint: `GET /v1/admin/raw-offers/{id|raw_offer_id}` — explain parsing/matching (incl. LLM attempted state)

---

## Phase 3 — Guides (LLM + whitelist)

- [ ] Таблица `country_sources` (whitelist URLs)
- [ ] Facts Extraction (GPT-4o-mini) → structured JSON
- [ ] Guide Composition → 3-7 steps + alerts
- [ ] Multi-language поддержка

---

## Phase 4 — SEO (Next.js ISR)

- [ ] `/[sku]/[country]` dynamic routes
- [ ] ISR с revalidate interval
- [ ] JSON-LD: Product + AggregateOffer
- [ ] hreflang tags

---

## Phase 5 — Admin & Observability

- [ ] Admin Console (Web UI в `apps/web`) для управления текущим `/v1/admin/*`
  - [ ] Security: добавить `ADMIN_TOKEN` и требовать `X-Admin-Token` для всех `/v1/admin/*` в production
  - [ ] `/admin` (Next.js) — отдельный layout + навигация (Tabs/Sidebar)
  - [ ] Dashboard:
    - [ ] Health (`/health`)
    - [ ] LLM config (`/v1/admin/debug/llm`)
    - [ ] FX debug (`/v1/admin/debug/fx`)
    - [ ] SerpAPI debug files list (`/v1/admin/debug/serpapi`)
  - [ ] Ingestion UI (`POST /v1/admin/ingest`):
    - [ ] форма (sku_key + country_code + min_confidence + toggles)
    - [ ] вывод stats + “Copy JSON”
  - [ ] Reconcile UI (`POST /v1/admin/reconcile`):
    - [ ] форма (limit/dry_run/country_code)
    - [ ] вывод stats + debug samples + LLM metrics
  - [ ] Raw Offer Explain UI (`GET /v1/admin/raw-offers/{ref}`):
    - [ ] форма (ref + include_candidates)
    - [ ] секции: rawOffer/deterministic/catalog/llm/debug
  - [ ] Golden SKUs UI:
    - [ ] list (`GET /v1/admin/skus`)
    - [ ] create (`POST /v1/admin/skus`)
    - [ ] view (`GET /v1/admin/skus/{sku_key}`)
  - [ ] Debug viewer:
    - [ ] list/view SerpAPI debug JSON files
  - [ ] Документация: `docs/13-admin-console.md`
  - [ ] Patterns management:
    - [ ] CRUD UI для `/v1/admin/patterns` (contract + condition phrases)
    - [ ] LLM suggest UI для `/v1/admin/patterns/suggest` + “apply selected phrases”

- [ ] Review queue для low-confidence matches
- [ ] Sentry + Checkly + Vercel Analytics

---

## 🚀 Немедленные следующие шаги

| # | Задача | Приоритет |
|---|--------|-----------|
| 1 | ~~Запустить docker-compose, проверить API~~ ✅ | Done |
| 2 | ~~Настроить Alembic миграции~~ ✅ | Done |
| 3 | ~~Seed данные для Golden SKU + iPhone 16 Pro~~ ✅ | Done |
| 4 | ~~Подключить фронтенд к API (react-query)~~ ✅ | Done |
| 5 | ~~Настроить Railway deployment~~ ✅ | Done |
| 6 | Запустить миграции на Railway (вручную или AUTO_MIGRATE=true) | 🟡 Medium |
| 7 | Настроить Neon/Supabase PostgreSQL (production) | 🟡 Medium |
| 8 | Настроить Upstash Redis (production) | 🟡 Medium |
| 9 | Настроить NEXT_PUBLIC_API_URL для production (Railway URL) | 🟡 Medium |

---

## Заметки

- ✅ Frontend мигрирован на Next.js 16 + Tailwind 4
- ✅ FastAPI backend создан в `services/api`
- ✅ Docker Compose настроен для локальной разработки
- ✅ pnpm настроен как package manager
- Прототип API (Fastify) в `apps/api/src/index.ts` — deprecated, для референса
- Shared Zod schemas в `packages/shared/src/index.ts` — сохраняем как контракт

## Vercel настройки

| Параметр | Значение |
|----------|----------|
| **Root Directory** | `apps/web` |
| **Framework Preset** | Next.js |
| **Build Command** | `pnpm build` |
| **Output Directory** | _(оставить пустым)_ |
| **Install Command** | `pnpm install` |

## Railway настройки (Backend)

| Параметр | Значение |
|----------|----------|
| **Root Directory** | `services/api` |
| **Builder** | Dockerfile |
| **Port** | 8080 |
