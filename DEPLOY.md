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
3. **Environment** → добавить переменные. Сначала четыре обязательные:

   | Ключ | Значение | Зачем |
   |------|----------|-------|
   | `CAMPUSLENS_USER_AGENT` | `CampusLens-AI/1.0 (LOCUS 2026; mailto:твоя@почта)` | Wikimedia режет анонимные запросы (429) |
   | `CAMPUSLENS_CORS_ORIGINS` | адрес фронта на Vercel **со схемой**: `https://имя.vercel.app` | без него браузер блокирует все запросы к API |
   | `CAMPUSLENS_AUTH_SECRET` | случайная строка, 32+ символа | без неё ключ подписи генерируется заново при каждом старте, и все разлогиниваются |
   | `CAMPUSLENS_DEMO_ACCOUNT` | `jury@locus.kz:locus2026demo` | демо-доступ для жюри, создаётся при старте |

   Секрет сгенерировать:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`

   > На шаге 1 адреса фронта ещё нет — поставь `http://localhost:3000`
   > и вернись сюда после шага 2.

   Дальше — ключ LLM, если нужно описание кампуса (шаг 6 ТЗ). Без ключа
   профиль собирается как обычно, просто без текста. Достаточно одного:

   | Ключ | Где взять |
   |------|-----------|
   | `GOOGLE_API_KEY` | <https://aistudio.google.com/apikey> (Gemini) |
   | `GROQ_API_KEY` | <https://console.groq.com/keys> |
   | `ANTHROPIC_API_KEY` | <https://console.anthropic.com> |

   Провайдер выбирается сам по тому, какой ключ задан (порядок: gemini,
   groq, anthropic). Задать явно — `CAMPUSLENS_LLM_PROVIDER`.

   Остальные переменные имеют рабочие значения по умолчанию, но их удобно
   задать явно — видно, куда сервис пишет:

   | Ключ | Значение |
   |------|----------|
   | `CAMPUSLENS_TOTAL_TIMEOUT` | `25` |
   | `CAMPUSLENS_REQUIRE_AUTH` | `true` |
   | `CAMPUSLENS_CACHE_ENABLED` | `true` |
   | `CAMPUSLENS_CACHE_DIR` | `/app/data/cache` |
   | `CAMPUSLENS_USERS_PATH` | `/app/data/users.json` |
   | `CAMPUSLENS_UPLOAD_DIR` | `/app/data/uploads` |
   | `CAMPUSLENS_SUBSCRIPTIONS_PATH` | `/app/data/subscriptions.json` |

   > `WORKDIR` образа — `/app`, поэтому значения по умолчанию (`data/…`)
   > и так ведут в те же каталоги. Каталоги сервис создаёт сам.

4. **Create Web Service**. После сборки проверить:
   `https://<имя>.onrender.com/api/health` → `{"status":"ok",...}`.
   Скопировать этот адрес — он нужен фронту.

**Про бесплатный тариф:** сервис засыпает после 15 минут простоя, первый
запрос после сна поднимает контейнер ~30–60 с. Перед показом жюри открой
`/api/health` заранее, чтобы сервис проснулся. Диск эфемерный — после
передеплоя пусты и кеш, и загруженные фото, и список зарегистрированных
пользователей. Демо-аккаунт из `CAMPUSLENS_DEMO_ACCOUNT` создаётся заново
при каждом старте, поэтому вход для жюри переживает передеплой; аккаунты,
заведённые вручную, — нет.

---

## 2. Фронтенд на Vercel

1. <https://vercel.com/new> → импортировать тот же репозиторий.
2. **Root Directory:** `web` — нажать **Edit** и выбрать папку.
   Обязательно: в корне репозитория нет `package.json`, и без этого
   Application Preset останется `Other`, а сборка упадёт. После смены
   папки пресет определится как **Next.js** сам; если нет — выбрать вручную.
3. **Environment Variables.** Vercel находит в корне `.env.example` и
   предлагает импортировать **все 15** переменных. Четырнадцать из них
   бэкендовые (`CAMPUSLENS_*`, ключи поисковых API) — их надо **удалить**.
   Оставить ровно одну:

   | Ключ | Значение |
   |------|----------|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://<имя>.onrender.com` (без слэша в конце) |

   > Переменная вшивается в бандл на этапе сборки. Если поменяешь её позже —
   > нужен **Redeploy**, простого рестарта мало.

   > **Ветка.** Vercel и Render берут default-ветку репозитория. Если на
   > GitHub она ещё не `main`, переключи: Settings → General → Default
   > branch. Иначе задеплоится не та ветка, и это не всегда заметно.
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
