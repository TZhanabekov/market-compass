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
| **FastAPI** (Python 3.11+) | REST API |
| **Docker** | Контейнеризация |
| **Railway** | Деплой, автоскейлинг |
| **Pydantic v2** | Схемы запросов/ответов |

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

### Текущая структура:
```
apps/
├── web/           # ✅ Next.js 16 (основной)
└── api/           # Node.js/Fastify прототип (требует миграции на FastAPI)
```

---

## 🔄 Текущие задачи

### Cleanup
- [x] ~~Удалить `apps/web-vite`~~ ✅
- [ ] Обновить документацию (docs/) с актуальной структурой

---

## Phase 0.2 — Инфраструктура бэкенда

### Создать FastAPI backend
- [ ] Создать `services/api` с FastAPI (Python 3.11+)
- [ ] Структура проекта:
```
services/api/
├── app/
│   ├── main.py              # FastAPI instance
│   ├── settings.py          # Pydantic Settings
│   ├── routes/
│   │   ├── ui.py            # GET /v1/ui/home
│   │   └── redirect.py      # GET /r/offers/{offerId}
│   ├── services/
│   │   ├── serpapi_client.py
│   │   ├── ranking.py
│   │   ├── dedup.py
│   │   └── trust.py
│   ├── stores/
│   │   ├── postgres.py
│   │   └── redis.py
│   ├── models/              # SQLAlchemy models
│   └── schemas/             # Pydantic schemas
├── tests/
├── Dockerfile
├── pyproject.toml
└── alembic/                 # Migrations
```

### Docker Compose для локальной разработки
- [ ] Dockerfile для FastAPI
- [ ] docker-compose.yml:
  - [ ] FastAPI app
  - [ ] PostgreSQL
  - [ ] Redis

### Настройка внешних сервисов
- [ ] PostgreSQL: создать базу в Neon или Supabase
- [ ] Upstash Redis: создать инстанс
- [ ] Vercel: подключить репозиторий для `apps/web`

---

## Phase 1 — Backend API (FastAPI)

### 1.1 База данных (PostgreSQL)
- [ ] SQLAlchemy models:
  - [ ] `golden_skus`
  - [ ] `merchants`
  - [ ] `offers`
  - [ ] `materialized_leaderboards`
- [ ] Alembic миграции
- [ ] Seed данные: Golden SKU для iPhone 16 Pro

### 1.2 Redis кеширование (Upstash)
- [ ] Кеш SerpAPI ответов (TTL 1-6h)
- [ ] Кеш курсов валют (TTL ~1h)
- [ ] Кеш UI payload (TTL 30-300s)
- [ ] Locks для hydration (TTL 30-120s)

### 1.3 API эндпоинты
- [ ] `GET /health`
- [ ] `GET /v1/ui/home?sku=...&home=...&minTrust=...&lang=...`
- [ ] `GET /r/offers/{offerId}` — redirect с lazy hydration

### 1.4 Курсы валют
- [ ] Интеграция с openexchangerates API
- [ ] Кеширование в Redis (TTL ~1 час)

---

## Phase 2 — SerpAPI интеграция

- [ ] SerpAPI клиент (google_shopping + immersive)
- [ ] Regex extraction для атрибутов iPhone
- [ ] GPT-4o-mini fallback для сложных случаев
- [ ] Trust Score (0-100)
- [ ] Ranking по effective price
- [ ] Scheduled refresh jobs

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

- [ ] Review queue для low-confidence matches
- [ ] Merchant management
- [ ] Sentry + Checkly + Vercel Analytics

---

## 🚀 Немедленные следующие шаги

| # | Задача | Приоритет |
|---|--------|-----------|
| 1 | Создать FastAPI backend scaffold в `services/api` | 🔴 High |
| 2 | Docker Compose (FastAPI + Postgres + Redis) | 🔴 High |
| 3 | Настроить Neon/Supabase PostgreSQL | 🟡 Medium |
| 4 | Настроить Upstash Redis | 🟡 Medium |
| 5 | Seed данные для Golden SKU | 🟡 Medium |

---

## Заметки

- ✅ Frontend мигрирован на Next.js 16 + Tailwind 4
- ✅ pnpm настроен как package manager
- Прототип API (Fastify) в `apps/api/src/index.ts` — для референса
- Shared Zod schemas в `packages/shared/src/index.ts` — сохраняем как контракт

## Vercel настройки

| Параметр | Значение |
|----------|----------|
| **Root Directory** | `apps/web` |
| **Framework Preset** | Next.js |
| **Build Command** | `pnpm build` |
| **Output Directory** | _(оставить пустым)_ |
| **Install Command** | `pnpm install` |
