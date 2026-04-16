# AI Vigil

[English](README.md) | [简体中文](README.zh-CN.md)

AI Vigil is an open-source monitoring console for OpenAI-compatible gateways such as `new-api`. It watches model availability, HTTP services, semantic content quality, regression golden sets, and alert delivery from one self-hosted dashboard.

> Previously named AI Eye Monitor in the codebase. The project goal is simple: know whether your AI gateway is alive, whether each model still works, and whether important model outputs are still correct.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3-42B883?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Why

AI systems fail in more ways than ordinary APIs. A gateway can be reachable while a specific model is broken, an embedding endpoint can return an empty vector, an ASR model can drift, or a business endpoint can return a valid HTTP 200 with useless content.

AI Vigil is built for that middle ground between uptime monitoring and quality evaluation:

- Discover and monitor models from one or many `new-api` instances.
- Run health checks for chat, embeddings, rerank, audio, image, moderation, custom HTTP, and ordinary services.
- Maintain Golden Sets for regression checks with rule-based assertions and optional AI evaluation.
- Send Webhook alerts for failures, recoveries, and daily inspection reports.
- Self-host with SQLite for small teams or MySQL for production-like deployments.

## Features

- **Multiple new-api instances**: manage test, staging, and production gateways from the console.
- **Model discovery**: sync `/v1/models`, match model IDs with rules, and auto-create checks.
- **Model availability checks**: chat, completion, vision, embedding, rerank, ASR, translation, TTS, image, edit, moderation, and custom HTTP.
- **HTTP checks**: method, headers, query, JSON/form/raw body, status code, text match, JSONPath, and latency validation.
- **AI content evaluation**: use an evaluator model to judge whether business responses satisfy semantic expectations.
- **Golden Set regression**: fixed cases, sample assets, JSON rules, prompt versions, score, confidence, and failure reasons.
- **Daily inspection report**: send a summary every day at 09:00 Asia/Shanghai through existing Webhook channels.
- **Webhook alerts**: failure threshold, cooldown, recovery notification, and optional HMAC signature.
- **Single-process console**: FastAPI serves the API and the built Vue dashboard.

## Screens and Modules

The dashboard includes:

- Login
- Overview
- Check management
- Run history
- Trends
- Quality regression
- Sample assets
- Model center
- Alert channels
- System settings

## Supported Check Types

| Check type | Endpoint | Purpose |
|---|---|---|
| `model_llm_chat` | `/v1/chat/completions` | Chat models |
| `model_llm_completion` | `/v1/completions` | Legacy completion models or gateways |
| `model_vision_chat` | `/v1/chat/completions` | Vision and multimodal models |
| `model_embedding` | `/v1/embeddings` | Text embedding models |
| `model_rerank` | `/v1/rerank` by default | Rerank models; override `endpoint` in request config if needed |
| `model_audio_transcription` | `/v1/audio/transcriptions` | Speech to text |
| `model_audio_translation` | `/v1/audio/translations` | Audio translation |
| `model_audio_speech` | `/v1/audio/speech` | Text to speech |
| `model_image_generation` | `/v1/images/generations` | Text to image |
| `model_image_edit` | `/v1/images/edits` | Image editing |
| `model_moderation` | `/v1/moderations` | Safety classification |
| `model_custom_http` | Custom URL | Non-standard AI services |
| `http_health` | Custom URL | Service health checks |
| `http_content_ai` | Custom URL | HTTP response plus AI semantic validation |

## Quick Start With Docker

Docker Compose with SQLite is the fastest way to try the project.

```bash
git clone https://github.com/kiedeng/ai-vigil.git
cd ai-vigil
cp .env.example .env
docker compose up --build -d
```

Open:

```text
http://127.0.0.1:8010
```

Default login values come from `.env.example`. Change them before exposing the service:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password
JWT_SECRET=replace-with-a-long-random-string
NEW_API_BASE_URL=http://your-new-api-host:3000
NEW_API_KEY=your-new-api-key
EVALUATOR_MODEL=deepseek-chat
```

Health check:

```bash
curl http://127.0.0.1:8010/healthz
```

### Docker Compose With MySQL

```bash
MYSQL_PASSWORD="change-me" MYSQL_ROOT_PASSWORD="change-root" \
docker compose -f docker-compose.mysql.yml up --build -d
```

## Local Development

### Backend

```bash
git clone https://github.com/kiedeng/ai-vigil.git
cd ai-vigil
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8010
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Development URL:

```text
http://127.0.0.1:5173
```

Production-style local run:

```bash
cd frontend
npm run build
cd ..
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8010
```

## Configuration

AI Vigil reads environment values from `.env`. Runtime settings can also be changed in the dashboard.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite under `data/` | SQLAlchemy database URL |
| `ADMIN_USERNAME` | `admin` | Dashboard admin username |
| `ADMIN_PASSWORD` | `admin123` | Dashboard admin password |
| `JWT_SECRET` | `replace-with-a-long-random-string` | JWT signing secret |
| `NEW_API_BASE_URL` | `http://localhost:3000` | Used to bootstrap the default new-api instance |
| `NEW_API_KEY` | empty | Used to bootstrap the default new-api instance key |
| `EVALUATOR_MODEL` | `deepseek-chat` | Default model for AI semantic evaluation |

When the database is empty, AI Vigil creates one default new-api instance from `NEW_API_BASE_URL` and `NEW_API_KEY`. After startup, manage additional instances in **Model Center**.

## Golden Set Regression

Golden Set checks answer a different question from uptime checks: not only “did the endpoint return,” but “is the returned content still correct?”

Each Golden Set defines a model, check type, evaluator prompt, and evaluator config. Each Golden Case defines input and expected output rules.

Example expected config:

```json
{
  "contains": "ok",
  "json_path": "$.status",
  "json_path_equals": "ok",
  "json_schema": {
    "required": ["status", "data"],
    "properties": {
      "status": { "type": "string" },
      "data": { "type": "object" }
    }
  },
  "ai_expectation": "The response must indicate service success and include valid business data."
}
```

Common evaluator config:

```json
{
  "min_confidence": 0.7,
  "always_ai": false
}
```

## Webhook Payloads

Failure and recovery alerts are sent as JSON:

```json
{
  "event_type": "failure",
  "check_id": 1,
  "check_name": "prod deepseek-chat",
  "check_type": "model_llm_chat",
  "status": "failure",
  "failure_count": 3,
  "duration_ms": 1200,
  "error": "new-api returned 500",
  "run_id": 42,
  "occurred_at": "2026-04-15T12:00:00"
}
```

Daily reports use `event_type: "daily_report"` and include:

- system alive marker
- check summary
- availability for the last 24 hours
- latency percentiles
- Golden Set pass rate
- new-api instance list
- current failures
- recent failed runs

If an alert channel has a `secret`, requests include `X-Monitor-Signature`, an HMAC-SHA256 signature of the request body.

### Enterprise WeChat Bot

Create an alert channel in **Alert channels**:

- Select `Enterprise WeChat Markdown` as the channel type.
- Paste the full robot webhook URL, for example `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...`.
- Keep Headers JSON as `{}`.
- Leave Secret empty.

Enterprise WeChat channels send `msgtype: markdown` messages. Test alerts and test daily reports now report the real delivery result; recent send attempts and failure reasons are visible in the alert event log.

## Database Migration

On startup, the backend initializes empty databases and upgrades existing Alembic-managed databases to the latest revision.

Manual migration:

```bash
source .venv/bin/activate
alembic -c backend/alembic.ini upgrade head
```

## Tests

Backend:

```bash
source .venv/bin/activate
python -m pytest -p no:cacheprovider tests/backend
```

Frontend:

```bash
cd frontend
npm run build
```

## Roadmap

- More notification targets such as Feishu, DingTalk, Slack, and email.
- Role-based access control.
- Built-in report history page.
- Prometheus metrics export.
- More visual charts for model quality regression.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing, and pull request guidance.

Good first contributions include:

- new check type examples
- alert channel adapters
- dashboard improvements
- docs and deployment recipes
- tests for edge cases

## Security

Please do not open public issues for sensitive vulnerabilities. See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
