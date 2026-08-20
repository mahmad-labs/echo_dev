# Configuration

Configuration is read from process environment variables after loading `.env` from the project root. Production secrets should be injected by the service manager or a secrets platform rather than committed to a file.

| Variable | Required | Purpose |
|---|---:|---|
| `DJANGO_ENV` | No | `development`, `staging`, or `production`; affects safe defaults. |
| `DJANGO_DEBUG` | Production: yes | Enable or disable Django debug mode. Must be false in production. |
| `DJANGO_SECRET_KEY` | Production: yes | Cryptographic signing secret. Use a high-entropy unique value. |
| `DJANGO_ALLOWED_HOSTS` | Production: yes | Comma-separated HTTP Host allowlist. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | HTTPS deployments | Comma-separated trusted origins including schemes. |
| `DATABASE_URL` | Production: yes | SQLite or PostgreSQL connection URL. |
| `DB_CONN_MAX_AGE` | No | Persistent PostgreSQL connection lifetime in seconds. |
| `DB_SSLMODE` | Production dependent | PostgreSQL SSL mode when not supplied in the URL. |
| `DEFAULT_TIMEZONE` | No | Django application timezone; defaults to UTC. |
| `CORS_ALLOWED_ORIGINS` | Cross-origin clients | Explicit comma-separated browser origins. |
| `SECURE_SSL_REDIRECT` | Production: yes | Redirect HTTP requests to HTTPS. |
| `SECURE_HSTS_SECONDS` | No | HSTS duration; production default is one year. |
| `MAX_UPLOAD_SIZE` | No | In-memory upload limit in bytes. |
| `JWT_ACCESS_MINUTES` | No | Access-token lifetime; default 15 minutes. |
| `JWT_REFRESH_DAYS` | No | Refresh-token lifetime; default 7 days. |
| `REDIS_URL` | Optional | Cache, Celery broker, and Celery result backend. |
| `CELERY_TASK_ALWAYS_EAGER` | No | Execute tasks inline when true. |
| `EMAIL_BACKEND` | No | Django email backend import path. |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP | SMTP server details. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP | SMTP credentials. |
| `EMAIL_USE_TLS` | SMTP | Enable STARTTLS. |
| `DEFAULT_FROM_EMAIL` | No | Default sender address. |
| `AI_PROVIDER_BASE_URL` | AI features | Base URL for an OpenAI-compatible API. |
| `AI_PROVIDER_API_KEY` | AI features | Provider bearer token. |
| `AI_PROVIDER_MODEL` | AI features | Default model identifier. |
| `AI_VISION_MODEL` | Screen/media vision | Optional vision-capable model; falls back to `AI_PROVIDER_MODEL`. |
| `ECHO_BROWSER_ENGINE` | Computer use | `chrome`, `chromium`, `edge`, or `firefox`. |
| `ECHO_BROWSER_BINARY` | Computer use | Optional explicit browser executable path. |
| `ECHO_BROWSER_REMOTE_URL` | Computer use | Optional Selenium Remote WebDriver endpoint. |
| `ECHO_BROWSER_HEADLESS` | Computer use | Run the controlled browser headlessly when true. |
| `ECHO_BROWSER_ALLOW_LOCALHOST` | Computer use | Explicitly permit localhost destinations. Disabled by default. |
| `ECHO_BROWSER_ALLOW_PRIVATE_NETWORKS` | Computer use | Explicitly permit private-network destinations. Disabled by default. |
| `ECHO_BROWSER_PAGELOAD_TIMEOUT` | Computer use | Browser page-load timeout in seconds. |
| `ECHO_BROWSER_SCRIPT_TIMEOUT` | Computer use | Browser script timeout in seconds. |
| `ECHO_BROWSER_MAX_WAIT` | Computer use | Maximum single browser wait action. |
| `ECHO_COMPUTER_USE_MAX_STEPS` | Computer use | Maximum steps in one operation. |
| `ECHO_COMPUTER_USE_MAX_REPLANS` | Computer use | Maximum evidence-driven replans after execution errors. |
| `ECHO_COMPUTER_USE_MAX_RUNTIME_SECONDS` | Computer use | Maximum operation runtime. |
| `ECHO_COMPUTER_UI_TREE_PROVIDER_CLASS` | Computer control | Optional dotted OS accessibility/UI-tree provider class. |
| `ECHO_DESKTOP_ACTION_PAUSE` | Computer control | Small pause applied between authorized desktop input actions. |
| `ECHO_DESKTOP_VERIFY_DELAY` | Computer control | Delay before post-action screen verification. |
| `VOICE_ACTIVE_SESSION_MINUTES` | Voice | Active continuous command window, clamped to 1–60 minutes. |
| `VOICE_SPEAKER_THRESHOLD` | Voice | Probabilistic enrolled-speaker cosine threshold. |
| `VOICE_SPEAKER_MIN_SAMPLES` | Voice | Minimum derived enrollment samples before speaker matching is active. |
| `VOICE_SPEAKER_MIN_QUALITY` | Voice | Minimum accepted enrollment quality score. |
| `VOICE_SPEAKER_PROVIDER_CLASS` | Voice | Optional dotted server-side speaker embedding provider; raw audio is not persisted solely for verification. |
| `ECHO_LOCAL_BACKGROUND_WORKERS` | Computer use | Bounded local executor worker count when Celery is not configured. |
| `ECHO_MEDIA_MAX_VISUAL_SAMPLES` | Media intelligence | Maximum rendered visual timeline samples per media analysis. |
| `ECHO_MEDIA_MAX_AUDIO_SAMPLES` | Media intelligence | Maximum accessible rendered-audio samples when captions are insufficient. |
| `ECHO_MEDIA_AUDIO_SAMPLE_SECONDS` | Media intelligence | Duration of each rendered-audio sample; capped by the runtime. |
| `ECHO_MEDIA_STT_PROVIDER` | Media intelligence | Optional server STT provider identifier for media audio; otherwise Echo uses a configured non-browser Voice STT provider when available. |
| `ECHO_MEDIA_MAX_TRANSCRIPT_CHARS` | Media intelligence | Maximum accessible transcript text retained per analysis. |
| `INTERNET_SEARCH_ENDPOINT` | Search features | JSON search endpoint accepting `q`, `type`, and `limit`. |
| `INTERNET_SEARCH_API_KEY` | Search features | Search-provider bearer token. |
| `VOICE_PROVIDER_BASE_URL` | Voice features | Base URL exposing `/transcribe` and `/synthesize`. |
| `VOICE_PROVIDER_API_KEY` | Voice features | Voice-provider bearer token. |
| `VOICE_MAX_AUDIO_BYTES` | No | Maximum accepted audio payload. |
| `LOG_LEVEL` | No | Root JSON logging threshold. |

IMAP account passwords are never stored directly in an Echo model. An `EmailAccount.configuration.password_env` value names the process environment variable containing the password. Provider keys should follow the same indirection principle where integrations are extended.
