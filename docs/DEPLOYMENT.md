# Deployment Guide

## 1. Railway API (Backend)

### Получение URL для API

1. Зайдите в **Railway Dashboard** → ваш проект
2. Откройте ваш **API service**
3. Перейдите на вкладку **Settings**
4. Найдите секцию **Networking** или **Public Domain**
5. Railway автоматически создает публичный домен вида: `https://your-service-name.up.railway.app`
6. Скопируйте этот URL - это ваш **API URL для продакшена**

### Настройка переменных окружения в Railway

В Railway Dashboard → ваш API service → **Variables**:

```
DATABASE_URL=<Railway автоматически создает>
REDIS_URL=<если используете Railway Redis>
CORS_ORIGINS=["https://your-vercel-app.vercel.app"]
AUTO_MIGRATE=true  # опционально, для авто-миграций
```

---

## 2. Vercel Frontend (Next.js)

### Настройка NEXT_PUBLIC_API_URL

1. Зайдите в **Vercel Dashboard** → ваш проект
2. Откройте **Settings** → **Environment Variables**
3. Добавьте переменную:
   - **Name**: `NEXT_PUBLIC_API_URL`
   - **Value**: `https://your-service-name.up.railway.app` (URL из Railway)
   - **Environment**: Production, Preview, Development (или только Production)
4. Сохраните и **redeploy** проект

### Локальная разработка

Для локальной разработки создайте файл `apps/web/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8080
```

Этот файл уже создан и добавлен в `.gitignore`.

---

## 3. Запуск миграций на Railway

### Вариант 1: Через скрипт (локально)

```bash
cd services/api
./run_migrations.sh
```

Скрипт:
- Создаст виртуальное окружение
- Установит зависимости
- Запустит миграции через Railway CLI (с env vars из Railway)

### Вариант 2: Автоматически при старте (рекомендуется)

В Railway Dashboard → ваш API service → **Variables**:

```
AUTO_MIGRATE=true
```

Миграции будут запускаться автоматически при каждом деплое.

### Вариант 3: Через Railway CLI (если есть доступ к контейнеру)

```bash
railway run alembic upgrade head
railway run python -m scripts.seed
```

---

## 4. Проверка работы

### Проверка API

```bash
# Health check
curl https://your-service-name.up.railway.app/health

# Home endpoint
curl "https://your-service-name.up.railway.app/v1/ui/home?sku=iphone-16-pro-256gb-black-new&home=DE&minTrust=80"
```

### Проверка Frontend

1. Откройте ваш Vercel deployment
2. Откройте DevTools → Network
3. Проверьте, что запросы идут на правильный Railway URL
4. Проверьте, что данные загружаются

---

## 5. CORS настройка

В Railway → API service → Variables:

```
CORS_ORIGINS=["https://your-vercel-app.vercel.app","http://localhost:3000"]
```

Важно: добавьте и production, и localhost для разработки.

---

## Схема деплоя

```
┌─────────────────┐         ┌─────────────────┐
│   Vercel        │         │    Railway       │
│   (Frontend)    │────────▶│    (Backend)     │
│                 │  API    │                  │
│ Next.js App     │  calls  │  FastAPI         │
│                 │         │  PostgreSQL      │
└─────────────────┘         └─────────────────┘
     │                              │
     │ NEXT_PUBLIC_API_URL          │ DATABASE_URL
     │ (env var)                    │ (auto from Railway)
     │                              │
     └──────────────────────────────┘
```
