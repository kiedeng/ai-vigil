<template>
  <div>
    <section class="section">
      <div class="toolbar">
        <strong>检查项</strong>
        <el-button type="primary" @click="openCreate">新增检查</el-button>
      </div>
      <el-alert
        class="form-help"
        type="info"
        :closable="false"
        show-icon
        title="使用提示"
        description="测试运行会写入历史并更新状态，但不会推送告警；正式运行和调度运行会按失败阈值推送告警。只检查接口存活请选择“健康接口”，需要语义判断才使用“接口内容 + AI”。"
      />
      <div class="filter-bar">
        <el-input v-model="filters.search" clearable placeholder="搜索名称、模型、URL" style="width: 220px" @keyup.enter="load" />
        <el-select v-model="filters.category" clearable placeholder="类别" style="width: 130px">
          <el-option label="模型" value="model" />
          <el-option label="HTTP" value="http" />
          <el-option label="AI 内容" value="ai" />
          <el-option label="音频" value="audio" />
          <el-option label="图片" value="image" />
        </el-select>
        <el-select v-model="filters.type" clearable placeholder="检查类型" style="width: 170px">
          <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.instance_id" clearable placeholder="实例" style="width: 150px">
          <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-select v-model="filters.enabled" clearable placeholder="启用" style="width: 110px">
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 120px">
          <el-option label="success" value="success" />
          <el-option label="failure" value="failure" />
          <el-option label="unknown" value="unknown" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
      </div>
      <el-table :data="checks" stripe>
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="类别" width="100">
          <template #default="{ row }"><el-tag>{{ checkCategory(row.type) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="类型" width="170">
          <template #default="{ row }">{{ typeLabel(row.type) }}</template>
        </el-table-column>
        <el-table-column label="实例" width="130">
          <template #default="{ row }">{{ instanceName(row.new_api_instance_id) }}</template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.state?.status)">{{ row.state?.status ?? 'unknown' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="toggle(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :loading="runningId === row.id" @click="testRun(row)">测试运行</el-button>
            <el-button size="small" type="warning" :loading="runningId === row.id" @click="run(row)">正式运行</el-button>
            <el-button size="small" @click="viewRuns(row)">历史</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, sizes, prev, pager, next"
        :total="pagination.total"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :page-sizes="[20, 50, 100]"
        @current-change="load"
        @size-change="load"
      />
    </section>

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑检查' : '新增检查'" width="1080px">
      <div class="check-form-layout">
        <el-form label-position="top" class="check-form-main">
          <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
          <div class="grid-two">
            <el-form-item label="类型">
              <el-select v-model="form.type" style="width: 100%">
                <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="模型名"><el-input v-model="form.model_name" placeholder="模型检查时填写" /></el-form-item>
          </div>
          <div class="grid-two">
            <el-form-item label="new-api 实例">
              <el-select v-model="form.new_api_instance_id" clearable placeholder="默认实例" style="width: 100%">
                <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="间隔秒"><el-input-number v-model="form.interval_seconds" :min="10" style="width: 100%" /></el-form-item>
          </div>
          <div class="grid-two">
            <el-form-item label="超时秒"><el-input-number v-model="form.timeout_seconds" :min="1" style="width: 100%" /></el-form-item>
            <el-form-item label="连续失败阈值"><el-input-number v-model="form.failure_threshold" :min="1" style="width: 100%" /></el-form-item>
          </div>
          <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
          <el-alert
            v-if="form.type === 'http_content_ai'"
            class="form-help"
            type="warning"
            :closable="false"
            title="接口内容 + AI 会额外调用 AI 校验模型。如果 evaluator 模型不可用，会显示 evaluator_error；只做状态码检查请改用“健康接口”。"
          />
          <el-form-item label="请求配置 JSON">
            <el-input v-model="requestConfigText" type="textarea" :rows="8" class="json-editor" />
          </el-form-item>
          <el-form-item label="校验配置 JSON">
            <el-input v-model="validationConfigText" type="textarea" :rows="7" class="json-editor" />
          </el-form-item>
          <el-form-item label="AI 配置 JSON">
            <el-input v-model="aiConfigText" type="textarea" :rows="5" class="json-editor" />
          </el-form-item>
        </el-form>

        <aside class="example-panel">
          <div class="example-title">{{ currentExample.title }}</div>
          <p class="example-description">{{ currentExample.description }}</p>
          <div class="example-block">
            <div class="example-block-title">请求配置案例</div>
            <pre>{{ formatExample(currentExample.request_config) }}</pre>
          </div>
          <div class="example-block">
            <div class="example-block-title">校验配置案例</div>
            <pre>{{ formatExample(currentExample.validation_config) }}</pre>
          </div>
          <div class="example-block">
            <div class="example-block-title">小 Tip</div>
            <p class="example-description">{{ currentExample.tip }}</p>
          </div>
          <el-button type="primary" style="width: 100%" @click="applyExample">应用当前案例</el-button>
        </aside>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="runsVisible" title="运行历史" width="900px">
      <el-table :data="runs" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="run_mode" label="模式" width="100" />
        <el-table-column prop="created_at" label="时间" width="190" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="duration_ms" label="耗时" width="90" />
        <el-table-column prop="error" label="错误" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';
import { api, parseJsonObject, statusType, type Check, type CheckRun, type CheckType, type NewApiInstance } from '../api';

interface FormState {
  name: string;
  type: CheckType;
  enabled: boolean;
  interval_seconds: number;
  timeout_seconds: number;
  failure_threshold: number;
  new_api_instance_id: number | null;
  model_name: string;
}

interface CheckExample {
  title: string;
  description: string;
  request_config: Record<string, unknown>;
  validation_config: Record<string, unknown>;
  ai_config: Record<string, unknown>;
  modelName?: string;
  tip: string;
}

const typeOptions: Array<{ label: string; value: CheckType }> = [
  { label: 'LLM Chat', value: 'model_llm_chat' },
  { label: 'LLM Completion', value: 'model_llm_completion' },
  { label: 'Vision 图像理解', value: 'model_vision_chat' },
  { label: 'Embedding 模型', value: 'model_embedding' },
  { label: 'Rerank 重排序', value: 'model_rerank' },
  { label: '语音转文字 ASR', value: 'model_audio_transcription' },
  { label: '语音翻译', value: 'model_audio_translation' },
  { label: '文字转语音 TTS', value: 'model_audio_speech' },
  { label: '文生图', value: 'model_image_generation' },
  { label: '图像编辑', value: 'model_image_edit' },
  { label: '内容安全 Moderation', value: 'model_moderation' },
  { label: '自定义模型 HTTP', value: 'model_custom_http' },
  { label: '健康接口', value: 'http_health' },
  { label: '接口内容 + AI', value: 'http_content_ai' }
];

const CHECK_EXAMPLES: Record<CheckType, CheckExample> = {
  model_llm_chat: {
    title: 'LLM Chat',
    description: '调用 /v1/chat/completions，检查对话模型是否返回非空内容。',
    modelName: 'deepseek-chat',
    request_config: { prompt: 'Reply with OK only.', payload: { temperature: 0, max_tokens: 128 } },
    validation_config: {},
    ai_config: {},
    tip: '适合模型在线性冒烟；更严格的质量判断建议放到 Golden Set。'
  },
  model_llm_completion: {
    title: 'LLM Completion',
    description: '调用 /v1/completions，适合旧 Completion 模型或旧网关。',
    modelName: 'text-davinci-003',
    request_config: { prompt: 'Reply with OK only.', payload: { temperature: 0, max_tokens: 64 } },
    validation_config: {},
    ai_config: {},
    tip: '如果模型实际是 Chat 接口，请选择 LLM Chat。'
  },
  model_vision_chat: {
    title: 'Vision 图像理解',
    description: '发送测试图片并要求模型返回描述。',
    modelName: 'qwen-vl-plus',
    request_config: { prompt: 'Describe this image in one short word.' },
    validation_config: {},
    ai_config: {},
    tip: '可在 request_config 里放 image_url 覆盖默认测试图。'
  },
  model_embedding: {
    title: 'Embedding 模型',
    description: '调用 /v1/embeddings，检查是否返回非空向量。',
    modelName: 'bge-m3',
    request_config: { input: 'health check' },
    validation_config: {},
    ai_config: {},
    tip: '只验证接口结构和向量非空，不比较向量语义质量。'
  },
  model_rerank: {
    title: 'Rerank 重排序',
    description: '调用 /v1/rerank，接口路径可通过 endpoint 覆盖。',
    modelName: 'bge-reranker-large',
    request_config: { endpoint: '/v1/rerank', query: 'health check', documents: ['service is healthy', 'service is unavailable'] },
    validation_config: {},
    ai_config: {},
    tip: '不同网关 rerank 路径差异较大，失败时先确认 endpoint。'
  },
  model_audio_transcription: {
    title: '语音转文字 ASR',
    description: '调用 /v1/audio/transcriptions，可配置真实音频 file_path。',
    modelName: 'whisper-1',
    request_config: { response_format: 'json', language: 'zh', require_text: false },
    validation_config: {},
    ai_config: {},
    tip: '样本管理上传音频后，可在 Golden Case 中用 sample_asset_id 做质量回归。'
  },
  model_audio_translation: {
    title: '语音翻译',
    description: '调用 /v1/audio/translations。',
    modelName: 'whisper-1',
    request_config: { response_format: 'json', require_text: false },
    validation_config: {},
    ai_config: {},
    tip: '真实音频建议走 Golden Set，普通检查只负责可用性。'
  },
  model_audio_speech: {
    title: '文字转语音 TTS',
    description: '调用 /v1/audio/speech，检查返回非空音频。',
    modelName: 'tts-1',
    request_config: { input: 'health check', voice: 'alloy' },
    validation_config: {},
    ai_config: {},
    tip: '如果网关 voice 参数不同，可在请求配置中覆盖。'
  },
  model_image_generation: {
    title: '文生图',
    description: '调用 /v1/images/generations，检查返回图片 URL 或 base64。',
    modelName: 'gpt-image-1',
    request_config: { prompt: 'A simple green circle icon on a white background', size: '512x512' },
    validation_config: {},
    ai_config: {},
    tip: '质量判断建议放到 Golden Set，避免频繁调度消耗过高。'
  },
  model_image_edit: {
    title: '图像编辑',
    description: '调用 /v1/images/edits，上传内置测试图片。',
    modelName: 'gpt-image-1',
    request_config: { prompt: 'Make the image brighter', size: '512x512' },
    validation_config: {},
    ai_config: {},
    tip: '可通过 Golden Case 绑定样本图片做稳定回归。'
  },
  model_moderation: {
    title: '内容安全 Moderation',
    description: '调用 /v1/moderations，检查 results 数组。',
    modelName: 'omni-moderation-latest',
    request_config: { input: 'This is a harmless health check message.' },
    validation_config: {},
    ai_config: {},
    tip: '适合检查安全分类模型是否仍可调用。'
  },
  model_custom_http: {
    title: '自定义模型 HTTP',
    description: '用于非标准 AI 服务接口。',
    request_config: { method: 'POST', url: 'http://127.0.0.1:9000/audio/parse', data: '{"sample_id":"demo"}' },
    validation_config: { expected_status_codes: [200], json_path: '$.code', json_path_equals: 0 },
    ai_config: {},
    tip: '支持 data、--data、--data-raw、--data-binary 这类 curl 风格字段。'
  },
  http_health: {
    title: '健康接口',
    description: '用于检查普通 HTTP 服务是否可用。',
    request_config: { method: 'GET', url: 'http://127.0.0.1:8080/healthz' },
    validation_config: { expected_status_codes: [200], json_path: '$.status', json_path_equals: 'ok' },
    ai_config: {},
    tip: '只需要状态码、JSONPath 或关键词校验时，用这个类型最稳。'
  },
  http_content_ai: {
    title: '接口内容 + AI',
    description: '先检查 HTTP，再调用 evaluator model 判断语义是否满足预期。',
    request_config: { method: 'GET', url: 'http://127.0.0.1:8080/api/health' },
    validation_config: { expected_status_codes: [200], max_latency_ms: 3000, ai_expectation: '响应必须表示服务健康，不能是错误页或无关内容。' },
    ai_config: { enabled: true },
    tip: '它依赖系统设置里的 AI 校验模型；如果 evaluator 返回 503，会显示 evaluator_error。'
  }
};

const checks = ref<Check[]>([]);
const instances = ref<NewApiInstance[]>([]);
const runs = ref<CheckRun[]>([]);
const runningId = ref<number | null>(null);
const dialogVisible = ref(false);
const runsVisible = ref(false);
const editing = ref<Check | null>(null);
const requestConfigText = ref('{}');
const validationConfigText = ref('{}');
const aiConfigText = ref('{}');

const filters = reactive({
  search: '',
  category: '',
  type: '' as CheckType | '',
  enabled: null as boolean | null,
  status: '',
  instance_id: null as number | null
});
const pagination = reactive({ page: 1, page_size: 20, total: 0 });

const form = reactive<FormState>({
  name: '',
  type: 'http_health',
  enabled: true,
  interval_seconds: 300,
  timeout_seconds: 120,
  failure_threshold: 3,
  new_api_instance_id: null,
  model_name: ''
});

const currentExample = computed(() => CHECK_EXAMPLES[form.type]);

async function load() {
  const [pageRows, instanceRows] = await Promise.all([
    api.checks({ ...filters, page: pagination.page, page_size: pagination.page_size }),
    api.instances()
  ]);
  checks.value = pageRows.items;
  pagination.total = pageRows.total;
  instances.value = instanceRows;
}

function typeLabel(type: CheckType) {
  return typeOptions.find((item) => item.value === type)?.label ?? type;
}

function checkCategory(type: CheckType) {
  if (type.includes('audio')) return '音频';
  if (type.includes('image') || type.includes('vision')) return '图片';
  if (type === 'http_content_ai') return 'AI 内容';
  if (type === 'http_health' || type === 'model_custom_http') return 'HTTP';
  return '模型';
}

function resetForm() {
  Object.assign(form, {
    name: '',
    type: 'http_health',
    enabled: true,
    interval_seconds: 300,
    timeout_seconds: 120,
    failure_threshold: 3,
    new_api_instance_id: instances.value.find((item) => item.is_default)?.id ?? null,
    model_name: ''
  });
  requestConfigText.value = JSON.stringify({ method: 'GET', url: '' }, null, 2);
  validationConfigText.value = JSON.stringify({ expected_status_codes: [200] }, null, 2);
  aiConfigText.value = '{}';
}

function formatExample(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2);
}

function applyExample() {
  const example = currentExample.value;
  if (example.modelName) form.model_name = example.modelName;
  requestConfigText.value = formatExample(example.request_config);
  validationConfigText.value = formatExample(example.validation_config);
  aiConfigText.value = formatExample(example.ai_config);
  ElMessage.success('已应用当前类型案例');
}

function openCreate() {
  editing.value = null;
  resetForm();
  dialogVisible.value = true;
}

function openEdit(row: Check) {
  editing.value = row;
  Object.assign(form, {
    name: row.name,
    type: row.type,
    enabled: row.enabled,
    interval_seconds: row.interval_seconds,
    timeout_seconds: row.timeout_seconds,
    failure_threshold: row.failure_threshold,
    new_api_instance_id: row.new_api_instance_id ?? null,
    model_name: row.model_name ?? ''
  });
  requestConfigText.value = JSON.stringify(row.request_config ?? {}, null, 2);
  validationConfigText.value = JSON.stringify(row.validation_config ?? {}, null, 2);
  aiConfigText.value = JSON.stringify(row.ai_config ?? {}, null, 2);
  dialogVisible.value = true;
}

function instanceName(id?: number | null) {
  if (!id) return '默认';
  return instances.value.find((item) => item.id === id)?.name ?? `#${id}`;
}

async function save() {
  try {
    const payload = {
      ...form,
      model_name: form.model_name || null,
      request_config: parseJsonObject(requestConfigText.value),
      validation_config: parseJsonObject(validationConfigText.value),
      ai_config: parseJsonObject(aiConfigText.value)
    };
    if (editing.value) await api.updateCheck(editing.value.id, payload);
    else await api.createCheck(payload);
    dialogVisible.value = false;
    ElMessage.success('已保存');
    await load();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败');
  }
}

async function toggle(row: Check) {
  await api.updateCheck(row.id, { enabled: row.enabled });
  ElMessage.success('状态已更新');
}

async function testRun(row: Check) {
  runningId.value = row.id;
  try {
    const result = await api.testRunCheck(row.id);
    ElMessage[result.status === 'success' ? 'success' : 'error'](`测试运行：${result.status}，不会推送告警`);
    await load();
  } finally {
    runningId.value = null;
  }
}

async function run(row: Check) {
  runningId.value = row.id;
  try {
    const result = await api.runCheck(row.id);
    ElMessage[result.status === 'success' ? 'success' : 'error'](`正式运行：${result.status}`);
    await load();
  } finally {
    runningId.value = null;
  }
}

async function viewRuns(row: Check) {
  runs.value = await api.runs(row.id);
  runsVisible.value = true;
}

async function remove(row: Check) {
  await ElMessageBox.confirm(`删除检查「${row.name}」？`, '确认删除', { type: 'warning' });
  await api.deleteCheck(row.id);
  ElMessage.success('已删除');
  await load();
}

onMounted(load);
</script>
