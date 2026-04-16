# AI Vigil

[English](README.md) | [简体中文](README.zh-CN.md)

AI Vigil 是一个开源的 AI 网关与模型质量监控控制台，适用于 `new-api` 以及其他 OpenAI 兼容接口。它不仅检查服务是否在线，也检查模型是否可用、业务接口返回内容是否正确、Golden Set 回归是否通过，并能通过 Webhook 发送告警和每日巡检报告。

> 项目代码里仍保留了早期名称 AI Eye Monitor。当前仓库名和开源项目名为 AI Vigil。

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3-42B883?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 为什么需要它

AI 服务的故障不只是“接口挂了”。很多时候网关还活着，但某个模型不可用；Embedding 返回空向量；ASR 转写质量变差；业务接口 HTTP 200 但内容已经不符合预期。

AI Vigil 想解决的是这类问题：

- new-api 有没有宕机？
- 测试环境、生产环境的模型是否都还能调用？
- 每个模型的核心能力是否仍然正常？
- 重要业务接口返回的内容是否仍然正确？
- 今天系统整体情况如何，有没有隐藏失败？

## 核心功能

- **多 new-api 实例**：可在控制台维护测试、生产等多个网关实例。
- **模型发现**：同步 `/v1/models`，用规则匹配模型类型，并可自动创建检查项。
- **模型可用性检查**：支持 Chat、Completion、Vision、Embedding、Rerank、ASR、TTS、图片、Moderation、自定义 HTTP 等。
- **HTTP 健康检查**：支持 method、headers、query、JSON/form/raw body、状态码、关键字、JSONPath、耗时校验。
- **AI 内容校验**：用 evaluator model 判断业务接口响应是否满足语义预期。
- **Golden Set 质量回归**：固定输入、固定期望、规则优先、AI 兜底，追踪模型输出是否退化。
- **每日巡检报告**：默认每天 09:00（Asia/Shanghai）通过 Webhook 发送系统摘要。
- **Webhook 告警**：支持连续失败阈值、冷却时间、恢复通知和 HMAC 签名。
- **自托管部署**：默认 SQLite，也支持 MySQL；可用 Docker Compose 一键启动。

## 控制台模块

- 登录
- 监控总览
- 检查管理
- 运行历史
- 指标趋势
- 质量回归
- 样本管理
- 模型中心
- 告警配置
- 系统设置

## 支持的检查类型

| 检查类型 | 调用接口 | 用途 |
|---|---|---|
| `model_llm_chat` | `/v1/chat/completions` | 对话模型 |
| `model_llm_completion` | `/v1/completions` | 旧 Completion 模型或旧网关 |
| `model_vision_chat` | `/v1/chat/completions` | 图像理解、多模态问答 |
| `model_embedding` | `/v1/embeddings` | 文本向量模型 |
| `model_rerank` | 默认 `/v1/rerank` | 检索重排序模型，可通过 `endpoint` 覆盖 |
| `model_audio_transcription` | `/v1/audio/transcriptions` | 语音转文字 |
| `model_audio_translation` | `/v1/audio/translations` | 语音翻译 |
| `model_audio_speech` | `/v1/audio/speech` | 文字转语音 |
| `model_image_generation` | `/v1/images/generations` | 文生图 |
| `model_image_edit` | `/v1/images/edits` | 图像编辑 |
| `model_moderation` | `/v1/moderations` | 内容安全分类 |
| `model_custom_http` | 自定义 URL | 非标准 AI 服务 |
| `http_health` | 自定义 URL | 普通服务健康检查 |
| `http_content_ai` | 自定义 URL | HTTP 响应 + AI 语义校验 |

## Docker 快速开始

默认 Docker Compose 使用 SQLite，适合最快体验。

```bash
git clone https://github.com/kiedeng/ai-vigil.git
cd ai-vigil
cp .env.example .env
docker compose up --build -d
```

访问：

```text
http://127.0.0.1:8010
```

健康检查：

```bash
curl http://127.0.0.1:8010/healthz
```

首次启动前建议修改 `.env`：

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password
JWT_SECRET=replace-with-a-long-random-string
NEW_API_BASE_URL=http://your-new-api-host:3000
NEW_API_KEY=your-new-api-key
EVALUATOR_MODEL=deepseek-chat
```

### Docker Compose + MySQL

```bash
MYSQL_PASSWORD="change-me" MYSQL_ROOT_PASSWORD="change-root" \
docker compose -f docker-compose.mysql.yml up --build -d
```

## 本地开发

### 后端

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

### 前端

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

开发模式访问：

```text
http://127.0.0.1:5173
```

生产式本地运行：

```bash
cd frontend
npm run build
cd ..
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8010
```

## 配置说明

AI Vigil 会读取 `.env`，也可以在控制台修改部分运行配置。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/ai_eye.db` | SQLAlchemy 数据库连接 |
| `ADMIN_USERNAME` | `admin` | 管理员用户名 |
| `ADMIN_PASSWORD` | `admin123` | 管理员密码 |
| `JWT_SECRET` | `replace-with-a-long-random-string` | JWT 签名密钥 |
| `NEW_API_BASE_URL` | `http://localhost:3000` | 初始化默认 new-api 实例 |
| `NEW_API_KEY` | 空 | 初始化默认 new-api 实例密钥 |
| `EVALUATOR_MODEL` | `deepseek-chat` | 默认 AI 语义评估模型 |

数据库为空时，系统会用 `NEW_API_BASE_URL` 和 `NEW_API_KEY` 创建一个默认 new-api 实例。后续可以在“模型中心”维护更多实例。

## Golden Set 质量回归

普通检查回答“接口是否能返回”，Golden Set 回答“输出是否仍然正确”。

Golden Set 定义模型、检查类型、评估 Prompt 和评估配置。Golden Case 定义固定输入和期望输出。

期望配置示例：

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
  "ai_expectation": "响应必须表示服务正常，并包含有效业务数据"
}
```

评估配置示例：

```json
{
  "min_confidence": 0.7,
  "always_ai": false
}
```

## Webhook 告警与日报

失败和恢复告警会发送 JSON：

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

每日巡检报告使用 `event_type: "daily_report"`，包含：

- 系统存活标识
- 检查项摘要
- 近 24 小时可用率
- 延迟分位
- Golden Set 通过率
- new-api 实例列表
- 当前失败项
- 最近失败运行

如果告警通道配置了 `secret`，请求头会包含 `X-Monitor-Signature`，值为请求 body 的 HMAC-SHA256 签名。

### 企业微信机器人

在“告警配置”中新建通道：

- 通道类型选择 `企业微信 Markdown`
- Webhook URL 填完整机器人地址，例如 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...`
- Headers JSON 保持 `{}`
- 签名 Secret 留空

企业微信通道会发送 `msgtype: markdown` 格式的消息。测试消息和测试日报会按真实发送结果提示成功或失败；最近发送记录、失败原因可在“告警配置”的“发送日志”中查看。

## 数据库迁移

后端启动时会自动初始化空库，并把已有 Alembic 数据库升级到最新版本。

手动迁移：

```bash
source .venv/bin/activate
alembic -c backend/alembic.ini upgrade head
```

## 测试

后端：

```bash
source .venv/bin/activate
python -m pytest -p no:cacheprovider tests/backend
```

前端：

```bash
cd frontend
npm run build
```

## 路线图

- 飞书、钉钉、Slack、邮件等更多通知方式。
- 角色权限控制。
- 内置日报历史页面。
- Prometheus 指标导出。
- 更丰富的质量回归趋势图。

## 贡献

欢迎贡献代码、文档、测试和使用反馈。请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

适合入门的贡献方向：

- 增加模型检查配置示例
- 改进控制台空状态
- 增加通知渠道适配
- 补充部署文档
- 增加边界场景测试

## 安全

请不要在公开 Issue 中提交敏感漏洞。详见 [SECURITY.md](SECURITY.md)。

## 许可证

MIT。详见 [LICENSE](LICENSE)。
