<template>
  <div>
    <section class="section">
      <div class="toolbar">
        <strong>检查项</strong>
        <el-button type="primary" @click="openCreate">新增检查</el-button>
      </div>
      <el-table :data="checks" stripe>
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="170" />
        <el-table-column label="实例" width="130">
          <template #default="{ row }">{{ instanceName(row.new_api_instance_id) }}</template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="160" show-overflow-tooltip />
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
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :loading="runningId === row.id" @click="run(row)">运行</el-button>
            <el-button size="small" @click="viewRuns(row)">历史</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑检查' : '新增检查'" width="1080px">
      <div class="check-form-layout">
        <el-form label-position="top" class="check-form-main">
          <el-form-item label="名称">
            <el-input v-model="form.name" />
          </el-form-item>
          <div class="grid-two">
            <el-form-item label="类型">
              <el-select v-model="form.type" style="width: 100%">
                <el-option label="LLM Chat" value="model_llm_chat" />
                <el-option label="LLM Completion" value="model_llm_completion" />
                <el-option label="Vision 图像理解" value="model_vision_chat" />
                <el-option label="Embedding 模型" value="model_embedding" />
                <el-option label="Rerank 重排序" value="model_rerank" />
                <el-option label="语音转文字 ASR" value="model_audio_transcription" />
                <el-option label="语音翻译" value="model_audio_translation" />
                <el-option label="文字转语音 TTS" value="model_audio_speech" />
                <el-option label="文生图" value="model_image_generation" />
                <el-option label="图像编辑" value="model_image_edit" />
                <el-option label="内容安全 Moderation" value="model_moderation" />
                <el-option label="自定义模型 HTTP" value="model_custom_http" />
                <el-option label="健康接口" value="http_health" />
                <el-option label="接口内容 + AI" value="http_content_ai" />
              </el-select>
            </el-form-item>
            <el-form-item label="模型名">
              <el-input v-model="form.model_name" placeholder="模型检查时填写" />
            </el-form-item>
          </div>
          <div class="grid-two">
            <el-form-item label="new-api 实例">
              <el-select v-model="form.new_api_instance_id" clearable placeholder="默认实例" style="width: 100%">
                <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="间隔秒">
              <el-input-number v-model="form.interval_seconds" :min="10" style="width: 100%" />
            </el-form-item>
          </div>
          <div class="grid-two">
            <el-form-item label="超时秒">
              <el-input-number v-model="form.timeout_seconds" :min="1" style="width: 100%" />
            </el-form-item>
            <el-form-item label="连续失败阈值">
              <el-input-number v-model="form.failure_threshold" :min="1" style="width: 100%" />
            </el-form-item>
          </div>
          <div class="grid-two">
            <el-form-item label="启用">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </div>
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
          <div v-if="currentExample.modelName" class="example-block">
            <div class="example-block-title">模型名示例</div>
            <code>{{ currentExample.modelName }}</code>
          </div>
          <div class="example-block">
            <div class="example-block-title">请求配置案例</div>
            <pre>{{ formatExample(currentExample.request_config) }}</pre>
          </div>
          <div class="example-block">
            <div class="example-block-title">校验配置案例</div>
            <pre>{{ formatExample(currentExample.validation_config) }}</pre>
          </div>
          <div class="example-block">
            <div class="example-block-title">AI 配置案例</div>
            <pre>{{ formatExample(currentExample.ai_config) }}</pre>
          </div>
          <el-button type="primary" style="width: 100%" @click="applyExample">应用当前案例</el-button>
        </aside>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="runsVisible" title="运行历史" width="820px">
      <el-table :data="runs" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="created_at" label="时间" width="190" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
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
  modelName?: string;
  request_config: Record<string, unknown>;
  validation_config: Record<string, unknown>;
  ai_config: Record<string, unknown>;
}

const CHECK_EXAMPLES: Record<CheckType, CheckExample> = {
  model_llm_chat: {
    title: 'LLM Chat',
    description: '调用 /v1/chat/completions，检查对话模型是否返回非空文本。',
    modelName: 'deepseek-chat',
    request_config: {
      prompt: 'Reply with OK only.',
      payload: {
        temperature: 0,
        max_tokens: 128
      }
    },
    validation_config: {},
    ai_config: {}
  },
  model_llm_completion: {
    title: 'LLM Completion',
    description: '调用 /v1/completions，适合仍使用旧 Completion 接口的模型或网关。',
    modelName: 'text-davinci-003',
    request_config: {
      prompt: 'Reply with OK only.',
      payload: {
        temperature: 0,
        max_tokens: 64
      }
    },
    validation_config: {},
    ai_config: {}
  },
  model_vision_chat: {
    title: 'Vision 图像理解',
    description: '调用 /v1/chat/completions，发送一张 1x1 测试图片并要求模型返回描述。',
    modelName: 'qwen-vl-plus',
    request_config: {
      prompt: 'Describe this image in one short word.',
      image_url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lV9m6wAAAABJRU5ErkJggg=='
    },
    validation_config: {},
    ai_config: {}
  },
  model_embedding: {
    title: 'Embedding 模型',
    description: '调用 /v1/embeddings，检查是否返回非空向量数组。',
    modelName: 'bge-m3',
    request_config: {
      input: 'health check'
    },
    validation_config: {},
    ai_config: {}
  },
  model_rerank: {
    title: 'Rerank 重排序',
    description: '调用常见的 /v1/rerank。该接口不是 OpenAI 官方标准，不同网关可用 endpoint 覆盖。',
    modelName: 'bge-reranker-large',
    request_config: {
      endpoint: '/v1/rerank',
      query: 'health check',
      documents: ['service is healthy', 'service is unavailable']
    },
    validation_config: {},
    ai_config: {}
  },
  model_audio_transcription: {
    title: '语音转文字 ASR',
    description: '调用 /v1/audio/transcriptions。默认上传内置静音 wav，只检查 text 字段；如配置真实音频可开启 require_text。',
    modelName: 'whisper-1',
    request_config: {
      response_format: 'json',
      language: 'zh',
      require_text: false
    },
    validation_config: {},
    ai_config: {}
  },
  model_audio_translation: {
    title: '语音翻译',
    description: '调用 /v1/audio/translations。默认上传内置静音 wav，只检查 text 字段；如配置真实音频可开启 require_text。',
    modelName: 'whisper-1',
    request_config: {
      response_format: 'json',
      require_text: false
    },
    validation_config: {},
    ai_config: {}
  },
  model_audio_speech: {
    title: '文字转语音 TTS',
    description: '调用 /v1/audio/speech，输入短文本，检查返回非空音频二进制。',
    modelName: 'tts-1',
    request_config: {
      input: 'health check',
      voice: 'alloy'
    },
    validation_config: {},
    ai_config: {}
  },
  model_image_generation: {
    title: '文生图',
    description: '调用 /v1/images/generations，检查返回图片 URL 或 base64。',
    modelName: 'gpt-image-1',
    request_config: {
      prompt: 'A simple green circle icon on a white background',
      size: '512x512'
    },
    validation_config: {},
    ai_config: {}
  },
  model_image_edit: {
    title: '图像编辑',
    description: '调用 /v1/images/edits，上传内置 1x1 PNG，检查返回编辑后的图片。',
    modelName: 'gpt-image-1',
    request_config: {
      prompt: 'Make the image brighter',
      size: '512x512'
    },
    validation_config: {},
    ai_config: {}
  },
  model_moderation: {
    title: '内容安全 Moderation',
    description: '调用 /v1/moderations，检查返回 results 数组。',
    modelName: 'omni-moderation-latest',
    request_config: {
      input: 'This is a harmless health check message.'
    },
    validation_config: {},
    ai_config: {}
  },
  model_custom_http: {
    title: '自定义模型 HTTP',
    description: '用于音频解析、结构化抽取等非标准模型接口。',
    request_config: {
      method: 'POST',
      url: 'http://127.0.0.1:9000/audio/parse',
      body_type: 'json',
      headers: {
        Authorization: 'Bearer service-token'
      },
      json_body: {
        audio_url: 'https://example.com/sample.wav',
        output_schema: 'meeting_minutes_v1'
      }
    },
    validation_config: {
      expected_status_codes: [200],
      json_path: '$.code',
      json_path_equals: 0,
      contains: 'segments',
      max_latency_ms: 10000
    },
    ai_config: {}
  },
  http_health: {
    title: '服务健康接口',
    description: '用于检查服务健康接口是否可访问，并校验状态字段和响应耗时。',
    request_config: {
      method: 'GET',
      url: 'http://127.0.0.1:8080/healthz',
      headers: {}
    },
    validation_config: {
      expected_status_codes: [200],
      json_path: '$.status',
      json_path_equals: 'ok',
      max_latency_ms: 1000
    },
    ai_config: {}
  },
  http_content_ai: {
    title: '业务接口 + AI 校验',
    description: '用于检查接口能返回内容，并让 evaluator model 判断内容是否符合业务预期。',
    request_config: {
      method: 'POST',
      url: 'http://127.0.0.1:8080/api/report',
      body_type: 'json',
      json_body: {
        user_id: 'demo-user',
        range: 'today'
      }
    },
    validation_config: {
      expected_status_codes: [200],
      max_latency_ms: 3000
    },
    ai_config: {
      enabled: true,
      evaluator_model: 'deepseek-chat',
      expectation: '响应必须包含有效报告内容，不能是空结果、错误页或无关文本。'
    }
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
  const [checkRows, instanceRows] = await Promise.all([api.checks(), api.instances()]);
  checks.value = checkRows;
  instances.value = instanceRows;
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
  if (example.modelName) {
    form.model_name = example.modelName;
  }
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
    if (editing.value) {
      await api.updateCheck(editing.value.id, payload);
    } else {
      await api.createCheck(payload);
    }
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

async function run(row: Check) {
  runningId.value = row.id;
  try {
    const result = await api.runCheck(row.id);
    ElMessage[result.status === 'success' ? 'success' : 'error'](`运行结果：${result.status}`);
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
