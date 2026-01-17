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
| **GPT-4o-mini** | Нормализация/дедупликация (сложные случаи), локализация контента |

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
- [ ] Интеграция с openexchangerates API (FX service)
- [ ] Кеширование в Redis (TTL ~1 час)
- [x] Добавлен FX сервис + Redis cache helpers (готово к подключению в ingestion/пересчёт price_usd)
- [x] Debug endpoint: `/v1/admin/debug/fx` для диагностики отсутствующих курсов (например EUR)

---

## Phase 2 — SerpAPI интеграция

- [x] SerpAPI клиент (структура для google_shopping + immersive)
- [x] Реальные вызовы SerpAPI (с кешированием в Redis, TTL 1-6h)
- [x] Fix: корректный выбор валюты для `extracted_price` (не использовать `alternative_price.currency`, если primary price в другой валюте)
- [x] Regex extraction для атрибутов iPhone (model/storage/color/condition)
- [ ] GPT-4o-mini fallback для сложных случаев (low-confidence)
- [x] Trust Score (0-100) — базовый алгоритм
- [x] Ranking по effective price
- [x] Ingestion service: SerpAPI → extraction → FX → dedup → DB
- [x] Admin endpoint: `POST /v1/admin/ingest` для ручного тестирования
- [ ] Scheduled refresh jobs (worker)
- [ ] ⚠️ Удалить seed-данные и заменить реальными из SerpAPI

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

- [ ] Admin panel для управления:
  - [ ] iPhone models (16 Pro, 16 Pro Max, будущие модели)
  - [ ] Golden SKUs (storage/color/condition варианты)
  - [ ] Merchants (добавление, верификация, blacklist)
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
