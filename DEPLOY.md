# Деплой CampusLens AI

Бэкенд — **Render** (Docker), фронтенд — **Vercel**. Оба бесплатные.
Порядок важен: сначала API, потом фронт, потом вернуться и дописать CORS.

---

## 1. Бэкенд на Render

1. <https://dashboard.render.com> → **New** → **Web Service** → подключить GitHub
   и выбрать репозиторий `diawx-6669/hackaton`, ветка `main`.
2. Render увидит `render.yaml` в корне и предложит Blueprint — согласиться.
   Если создаёшь сервис вручную, задай:
   - **Language / Runtime:** Docker
   - **Dockerfile Path:** `./api/Dockerfile`
   - **Docker Build Context Directory:** `./api`
   - **Health Check Path:** `/api/health`
   - **Instance Type:** Free
3. **Environment** → добавить переменные:

   | Ключ | Значение |
   |------|----------|
   | `CAMPUSLENS_USER_AGENT` | `CampusLens-AI/1.0 (LOCUS 2026; mailto:твоя@почта)` |
   | `CAMPUSLENS_CORS_ORIGINS` | пока `http://localhost:3000`, поправим на шаге 3 |
   | `CAMPUSLENS_TOTAL_TIMEOUT` | `25` |
   | `CAMPUSLENS_CACHE_ENABLED` | `true` |
   | `CAMPUSLENS_CACHE_DIR` | `/app/data/cache` |

   > `CAMPUSLENS_USER_AGENT` обязателен: Wikimedia режет анонимные запросы (429).
   > Если забыть, сервис стартует, но в логе будет предупреждение.

4. **Create Web Service**. После сборки проверить:
   `https://<имя>.onrender.com/api/health` → `{"status":"ok",...}`.
   Скопировать этот адрес — он нужен фронту.

**Про бесплатный тариф:** сервис засыпает после 15 минут простоя, первый
запрос после сна поднимает контейнер ~30–60 с. Перед показом жюри открой
`/api/health` заранее, чтобы сервис проснулся. Диск эфемерный — после
передеплоя кеш пуст, это нормально.

---

## 2. Фронтенд на Vercel

1. <https://vercel.com/new> → импортировать тот же репозиторий.
2. **Root Directory:** `web` (обязательно, иначе сборка не найдёт проект).
   Framework Preset определится как Next.js сам.
3. **Environment Variables:**

   | Ключ | Значение |
   |------|----------|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://<имя>.onrender.com` (без слэша в конце) |

   > Переменная вшивается в бандл на этапе сборки. Если поменяешь её позже —
   > нужен **Redeploy**, простого рестарта мало.
4. **Deploy**. Получишь адрес вида `https://hackaton-xxx.vercel.app`.

---

## 3. Вернуться на Render и открыть CORS

В переменных сервиса заменить:

```
CAMPUSLENS_CORS_ORIGINS = https://hackaton-xxx.vercel.app
```

Сохранить → Render передеплоит сам. Без этого браузер заблокирует все
запросы к API с ошибкой CORS, хотя сам API будет работать.

Можно указать несколько адресов через запятую — например, прод и превью-домен.

---

## 4. Проверка после деплоя

```bash
curl https://<имя>.onrender.com/api/health
curl "https://<имя>.onrender.com/api/resolve?q=КБТУ"
```

Затем открыть сайт на Vercel и собрать профиль любого вуза. Должно работать
и с телефона.

---

## Частые ошибки

| Симптом | Причина | Что сделать |
|---------|---------|-------------|
| Сайт открывается, но профиль не собирается; в консоли `CORS policy` | `CAMPUSLENS_CORS_ORIGINS` не содержит домен Vercel | Шаг 3 |
| Первый запрос висит минуту | Бесплатный Render усыпил сервис | Прогреть `/api/health` заранее |
| `429` от Wikimedia в логах Render | Не задан `CAMPUSLENS_USER_AGENT` | Шаг 1.3 |
| Фронт стучится на `localhost:8000` | `NEXT_PUBLIC_API_BASE_URL` не задан или не пересобрано | Задать и нажать Redeploy |
| Vercel: «No Next.js version detected» | Не выставлен Root Directory | Поставить `web` |
