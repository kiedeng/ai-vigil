# AI Eye Monitor

AI Eye Monitor 是一个独立的智能监控系统，用于监控 new-api 模型、服务健康接口，以及需要 AI 判定内容是否正确的业务接口。

## 功能

- new-api 单实例模型发现：同步 `/v1/models`，用控制台规则匹配 LLM、Embedding 和自定义模型。
- 模型可用性检查：LLM 调用 `/v1/chat/completions`，Embedding 调用 `/v1/embeddings`。
- 通用 HTTP 检查：支持 method、headers、query、JSON/form/raw body、状态码、关键字、JSONPath、耗时校验。
- AI 内容校验：业务接口响应可复用 new-api 中的 evaluator model 做语义判断。
- 告警：通用 Webhook，支持连续失败阈值、冷却时间、恢复通知和 HMAC 签名。
- 控制台：登录、总览、检查管理、运行历史、模型中心、告警配置、系统设置。
- 存储：默认 SQLite，可通过 `.env` 切换 MySQL。

## 支持的模型检查类型

| 检查类型 | 调用接口 | 用途 |
|---|---|---|
| `model_llm_chat` | `/v1/chat/completions` | LLM 对话模型 |
| `model_llm_completion` | `/v1/completions` | 旧 Completion 模型或旧网关 |
| `model_vision_chat` | `/v1/chat/completions` | 图像理解、多模态问答 |
| `model_embedding` | `/v1/embeddings` | 文本向量模型 |
| `model_rerank` | 默认 `/v1/rerank` | 检索重排序模型；该接口不是 OpenAI 官方标准，可在请求配置里改 `endpoint` |
| `model_audio_transcription` | `/v1/audio/transcriptions` | 语音转文字 |
| `model_audio_translation` | `/v1/audio/translations` | 语音翻译 |
| `model_audio_speech` | `/v1/audio/speech` | 文字转语音 |
| `model_image_generation` | `/v1/images/generations` | 文生图 |
| `model_image_edit` | `/v1/images/edits` | 图像编辑 |
| `model_moderation` | `/v1/moderations` | 内容安全分类 |
| `model_custom_http` | 自定义 URL | 音频解析成结构化格式、文档解析、视频理解等非标准接口 |

## 质量回归、AI 校验和样本

专业监控不只判断“接口能返回”，还需要判断“返回是否正确”。当前系统已内置：

质量回归模块解决的是“模型还能不能稳定输出正确结果”。普通检查偏可用性，例如模型有没有返回、接口是不是 200；质量回归偏正确性，例如同一个抽取 prompt 今天还能不能返回符合 JSON Schema 的结果，ASR 同一段音频还能不能转成预期内容，报告生成是否仍包含关键字段。

核心概念：

- Golden Set：一组固定回归用例，通常对应一个模型或一个业务接口。
- Golden Case：Golden Set 里的单条用例，包含固定输入和期望结果。
- 输入配置：这次要怎么调用模型或接口。
- 期望配置：怎么判断输出正确，优先用规则，必要时用 AI evaluator 判断语义。

- Golden Set：每个集合绑定一个模型和检查类型，集合下维护多条标准用例。
- 规则校验：用例可配置 `contains`、`not_contains`、`regex`、`json_path`、`json_path_equals`、简化 `json_schema`。
- AI 兜底：用例可配置 `ai_expectation`，规则失败时调用 evaluator model 做语义判定。
- AI Prompt 版本：控制台可维护 evaluator prompt 的 `name/version/active/template/schema`。
- 置信度：AI 判定要求返回 `passed/confidence/score/reason`，可在 Golden Set 的 `evaluator_config.min_confidence` 设置阈值。
- 样本管理：支持上传音频、图片、文档等样本；同一 `logical_name` 每次上传自动生成新版本。

Golden Case 的期望配置示例：

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

音频、图片、文档类用例可以绑定样本 ID，也可以在输入配置里直接指定样本路径：

```json
{
  "file_path": "/mnt/d/1/ai-eye/data/samples/asr_v1_demo.wav",
  "require_text": true
}
```

### Golden Set 使用方式

Golden Set 的类型和普通检查项使用同一套执行器，支持 `model_llm_chat`、`model_llm_completion`、`model_vision_chat`、`model_embedding`、`model_rerank`、`model_audio_transcription`、`model_audio_translation`、`model_audio_speech`、`model_image_generation`、`model_image_edit`、`model_moderation`、`model_custom_http`、`http_health`、`http_content_ai`。

推荐流程：

1. 在“AI 评估 Prompt 版本”里维护 evaluator prompt。模板里保留 `{expectation}` 和 `{response_text}` 两个变量，并要求模型只返回 JSON：`passed/confidence/score/reason`。
2. 新建 Golden Set，填写模型名、检查类型和评估配置。`AI 评估 Prompt` 留空时，系统自动使用 `name=default` 且 `active=true` 的最新版本；指定 Prompt ID 时，该集合固定使用那个版本。
3. 在 Golden Set 下新增 Golden Case。`输入配置 JSON` 就是该类型的请求配置；`期望配置 JSON` 是质量判断规则。
4. 点击 Golden Set 的“运行”，系统会逐条执行用例并写入 Golden Run。
5. 在“指标趋势”里查看 Golden 通过率，在 Golden Set 详情里查看每次失败原因、规则结果和 AI 判定结果。

Golden Set 的 `评估配置 JSON` 常用字段：

```json
{
  "min_confidence": 0.7,
  "always_ai": false
}
```

- `min_confidence`：AI 返回的置信度低于该值时，即使 `passed=true` 也判失败。
- `always_ai=false`：规则校验失败时才启用 AI 兜底。
- `always_ai=true`：规则通过后也继续调用 AI，用于更严格的语义质量回归。

Golden Case 中规则优先、AI 兜底。示例：

```json
{
  "json_path": "$.status",
  "json_path_equals": "ok",
  "ai_expectation": "响应必须表示任务成功，不能是错误页、空结果或无关内容。"
}
```

## WSL / Linux 快速开始

进入项目目录：

```bash
cd /mnt/d/1/ai-eye
```

创建 Linux 虚拟环境。不要复用 Windows 里的 `.venv`：

```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

初始化环境配置：

```bash
cp .env.example .env
```

如果使用默认 SQLite，把 `.env` 中的 Windows 路径改成 WSL 路径：

```bash
sed -i 's#sqlite:///D:/1/ai-eye/data/ai_eye.db#sqlite:////mnt/d/1/ai-eye/data/ai_eye.db#' .env
```

编辑 `.env`：

```bash
nano .env
```

至少修改这些值：

```env
ADMIN_PASSWORD="your-admin-password"
JWT_SECRET="replace-with-a-long-random-string"
NEW_API_BASE_URL="http://your-new-api-host:3000"
NEW_API_KEY="your-new-api-key"
EVALUATOR_MODEL="deepseek-chat"
```

如需 MySQL，改为类似：

```env
DATABASE_URL="mysql+pymysql://ai_eye:password@127.0.0.1:3306/ai_eye?charset=utf8mb4"
```

## 构建前端

```bash
cd /mnt/d/1/ai-eye/frontend
npm install
npm run build
```

构建完成后，后端会托管 `frontend/dist`。

## 启动服务

生产式本地启动，一个后端进程同时提供 API 和控制台页面：

```bash
cd /mnt/d/1/ai-eye
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8010
```

访问：

```text
http://127.0.0.1:8010
```

健康检查：

```bash
curl http://127.0.0.1:8010/healthz
```

后台运行可以用：

```bash
cd /mnt/d/1/ai-eye
source .venv/bin/activate
nohup python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8010 > logs/uvicorn.log 2>&1 &
```

停止后台进程：

```bash
pkill -f "uvicorn backend.app.main:app"
```

## 开发模式

终端 1 启动后端：

```bash
cd /mnt/d/1/ai-eye
source .venv/bin/activate
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8010
```

终端 2 启动前端：

```bash
cd /mnt/d/1/ai-eye/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

开发模式访问：

```text
http://127.0.0.1:5173
```

## 数据库迁移

开发阶段首次启动会自动 `create_all` 并写入 Alembic 版本号，方便空库直接运行。需要显式迁移时使用 Alembic：

```bash
cd /mnt/d/1/ai-eye
source .venv/bin/activate
alembic -c backend/alembic.ini upgrade head
```

如果你之前已经启动过旧版本，SQLite 里已经有 `checks` 等基础表，但没有 `alembic_version`，直接 `upgrade head` 会报 `table checks already exists`。这是旧库没有迁移版本标记导致的，一次性修复命令如下：

```bash
cd /mnt/d/1/ai-eye
source .venv/bin/activate
alembic -c backend/alembic.ini stamp 0001_initial
alembic -c backend/alembic.ini upgrade head
```

如果你在升级前已经启动过包含质量回归功能的新后端，`sample_assets`、`golden_sets` 等表可能已经被开发模式自动建好。这时只需要使用当前代码再次执行：

```bash
alembic -c backend/alembic.ini upgrade head
```

## 测试

后端测试：

```bash
cd /mnt/d/1/ai-eye
source .venv/bin/activate
python -m pytest -p no:cacheprovider tests/backend
```

前端构建校验：

```bash
cd /mnt/d/1/ai-eye/frontend
npm run build
```

## HTTP 检查配置示例

请求配置：

```json
{
  "method": "GET",
  "url": "https://example.com/health",
  "headers": {
    "X-App": "ai-eye"
  },
  "query": {
    "verbose": "1"
  }
}
```

校验配置：

```json
{
  "expected_status_codes": [200],
  "contains": "ok",
  "json_path": "$.status",
  "json_path_equals": "ok",
  "max_latency_ms": 1000
}
```

AI 校验配置：

```json
{
  "enabled": true,
  "evaluator_model": "deepseek-chat",
  "expectation": "响应内容必须表示服务正常，并包含有效业务数据"
}
```

## Webhook Payload

告警发送 JSON：

```json
{
  "event_type": "failure",
  "check_id": 1,
  "check_name": "new-api deepseek-chat",
  "check_type": "model_llm_chat",
  "status": "failure",
  "failure_count": 3,
  "duration_ms": 1200,
  "error": "new-api returned 500",
  "run_id": 42,
  "occurred_at": "2026-04-15T12:00:00"
}
```

如果通道配置了 `secret`，请求头会带 `X-Monitor-Signature`，值为 payload body 的 HMAC-SHA256。

## 多 new-api 实例

系统支持在“模型中心”维护多个 new-api 实例，例如测试环境和生产环境。每个实例包含名称、Base URL、API Key、启用状态和默认标记。API Key 会保存在数据库中，但接口响应和页面只展示“是否已配置”，不会返回明文。

首次启动空库时，系统会用 `.env` 中的 `NEW_API_BASE_URL` 和 `NEW_API_KEY` 创建一个 `default` 实例，用于兼容旧配置。检查项、Golden Set 和模型同步都可以选择绑定具体实例；未选择时回退默认实例。

## 每日巡检报告

系统默认每天 09:00（Asia/Shanghai）向所有启用的 Webhook 通道发送巡检报告。报告 payload 的 `event_type` 为 `daily_report`，包含系统存活标识、近 24 小时可用率、失败次数、延迟分位、Golden 通过率、new-api 实例列表、当前失败项和近 24 小时失败摘要。

可以在“系统设置”里关闭日报或调整发送时间，也可以在“告警配置”里点击“发送测试日报”立即验证 Webhook。

## Docker 部署

### Docker Compose + SQLite

默认方式会构建前端并由后端容器托管静态页面，数据库写入宿主机 `./data`。

```bash
cd /mnt/d/aicode/ai-eye
docker compose up --build -d
```

访问：

```text
http://127.0.0.1:8010
```

查看健康检查：

```bash
curl http://127.0.0.1:8010/healthz
```

### Docker Compose + MySQL

如需 MySQL：

```bash
cd /mnt/d/aicode/ai-eye
MYSQL_PASSWORD="change-me" MYSQL_ROOT_PASSWORD="change-root" docker compose -f docker-compose.mysql.yml up --build -d
```

应用会使用：

```text
mysql+pymysql://ai_eye:${MYSQL_PASSWORD}@mysql:3306/ai_eye?charset=utf8mb4
```

### 常用环境变量

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password
JWT_SECRET=replace-with-a-long-random-string
NEW_API_BASE_URL=http://your-new-api-host:3000
NEW_API_KEY=your-new-api-key
EVALUATOR_MODEL=deepseek-chat
```

Docker 首次启动空库时，会用 `NEW_API_BASE_URL` 和 `NEW_API_KEY` 初始化默认 new-api 实例。后续建议在控制台“模型中心”维护多个实例。
