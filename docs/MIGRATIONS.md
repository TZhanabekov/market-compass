# Database Migrations Guide

## Проблема с Railway Internal Domains

Railway использует внутренние домены (например, `postgres.railway.internal`) для подключения между сервисами внутри Railway сети. Эти домены **недоступны с локальной машины**, поэтому запуск миграций через `railway run` может не работать.

## Решения

### ✅ Вариант 1: AUTO_MIGRATE=true (Рекомендуется)

Самый простой способ - миграции запускаются автоматически при каждом деплое.

1. **Railway Dashboard** → ваш API service → **Variables**
2. Добавьте переменную:
   - **Name**: `AUTO_MIGRATE`
   - **Value**: `true`
3. Сохраните
4. При следующем деплое миграции запустятся автоматически

**Преимущества:**
- Автоматически при каждом деплое
- Работает внутри Railway сети
- Не требует локальных действий

**Недостатки:**
- Миграции запускаются при каждом деплое (может быть медленнее)
- Если миграция упадет, деплой может не завершиться

---

### ✅ Вариант 2: Railway Shell (Если доступен)

Запуск миграций внутри Railway контейнера.

1. **Railway Dashboard** → ваш API service → **Deployments**
2. Откройте последний deployment
3. Найдите кнопку **"Shell"** или **"Execute Command"**
4. Запустите:
   ```bash
   alembic upgrade head
   python -m scripts.seed
   ```

**Преимущества:**
- Работает внутри Railway сети
- Полный доступ к окружению

**Недостатки:**
- Может быть недоступно в зависимости от плана Railway

---

### ✅ Вариант 3: Railway CLI (Может не работать)

Попытка запуска через `railway run`:

```bash
cd services/api
./run_migrations.sh
```

**Внимание:** Может не работать из-за внутренних доменов Railway.

---

### ✅ Вариант 4: Локальная разработка

Для локальной разработки используйте отдельный скрипт:

```bash
cd services/api
./run_migrations_local.sh
```

Этот скрипт использует локальный `.env` файл и подключается к локальной базе данных (docker-compose).

---

## Проверка миграций

После запуска миграций проверьте:

```bash
# Через Railway CLI
railway run python -c "from app.stores.postgres import get_session; import asyncio; asyncio.run(get_session().__anext__())"

# Или через API endpoint
curl https://your-api.railway.app/health
```

---

## Рекомендация

**Используйте AUTO_MIGRATE=true** для продакшена. Это самый надежный способ, который работает всегда.

Для локальной разработки используйте `run_migrations_local.sh` с docker-compose.
