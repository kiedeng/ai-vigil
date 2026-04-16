<template>
  <div>
    <section class="section">
      <div class="toolbar">
        <strong>Golden Set</strong>
        <el-button type="primary" @click="openSetCreate">新增集合</el-button>
      </div>
      <el-alert
        class="form-help"
        type="info"
        :closable="false"
        show-icon
        title="质量回归用于判断模型输出有没有变差"
        description="普通检查只判断接口是否可用；质量回归会用固定输入反复测试模型，并用规则或 AI 判断输出是否仍符合预期。Golden Set 是一组用例，Golden Case 是其中一条固定输入和期望结果。"
      />
      <el-table :data="sets" stripe @row-click="selectSet">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="实例" width="130">
          <template #default="{ row }">{{ instanceName(row.new_api_instance_id) }}</template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="160" />
        <el-table-column prop="check_type" label="类型" min-width="180" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :loading="runningSetId === row.id" @click.stop="runSet(row)">运行</el-button>
            <el-button size="small" @click.stop="openSetEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click.stop="removeSet(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="selected" class="section">
      <div class="toolbar">
        <strong>用例：{{ selected.name }}</strong>
        <el-button @click="openCaseCreate">新增用例</el-button>
      </div>
      <el-table :data="detail?.cases ?? []" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="sample_asset_id" label="样本 ID" width="100" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">{{ row.enabled ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openCaseEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeCase(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="selected" class="section">
      <div class="toolbar">
        <strong>最近回归结果</strong>
        <el-button @click="loadRuns">刷新</el-button>
      </div>
      <el-alert
        class="form-help"
        type="info"
        :closable="false"
        show-icon
        title="结果说明"
        description="状态表示这条 Golden Case 是否通过；分数和置信度来自 AI evaluator，未启用 AI 时分数只按通过/失败记为 1 或 0；错误列只显示最终失败原因。"
      />
      <el-table :data="runs" stripe>
        <el-table-column prop="id" label="Run ID" width="90" />
        <el-table-column prop="case_id" label="Case ID" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="score" label="分数" width="90" />
        <el-table-column prop="confidence" label="置信度" width="100" />
        <el-table-column prop="duration_ms" label="耗时 ms" width="100" />
        <el-table-column prop="error" label="失败原因" show-overflow-tooltip />
      </el-table>
    </section>

    <section class="section">
      <div class="toolbar">
        <strong>AI 评估 Prompt 版本</strong>
        <el-button @click="openPromptCreate">新增 Prompt</el-button>
      </div>
      <el-table :data="prompts" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="version" label="版本" width="90" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">{{ row.active ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="prompt_template" label="模板" show-overflow-tooltip />
        <el-table-column label="操作" width="100">
          <template #default="{ row }"><el-button size="small" @click="openPromptEdit(row)">编辑</el-button></template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="setDialog" :title="editingSet?.id ? '编辑集合' : '新增集合'" width="760px">
      <el-form label-position="top">
        <div class="grid-two">
          <el-form-item label="名称"><el-input v-model="setForm.name" /></el-form-item>
          <el-form-item label="模型名"><el-input v-model="setForm.model_name" /></el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item label="new-api 实例">
            <el-select v-model="setForm.new_api_instance_id" clearable placeholder="默认实例" style="width: 100%">
              <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="setForm.check_type" style="width: 100%">
              <el-option
                v-for="option in checkTypeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item label="AI 评估 Prompt">
            <el-select v-model="setForm.evaluator_prompt_id" clearable placeholder="默认使用最新启用 default" style="width: 100%">
              <el-option
                v-for="prompt in prompts"
                :key="prompt.id"
                :label="`${prompt.name} v${prompt.version} #${prompt.id}${prompt.active ? '' : '（停用）'}`"
                :value="prompt.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="启用"><el-switch v-model="setForm.enabled" /></el-form-item>
        </div>
        <el-alert
          class="form-help"
          type="info"
          :closable="false"
          show-icon
          title="Golden Set 用法"
          description="集合只定义模型、检查类型和 AI 评估配置；真正的标准输入和期望输出放在下面的 Golden Case 里。Prompt 未选择时，会自动使用 active=true 的 default 最新版本。"
        />
        <el-form-item label="描述"><el-input v-model="setForm.description" /></el-form-item>
        <el-form-item label="评估配置 JSON">
          <el-input v-model="setEvaluatorText" type="textarea" :rows="7" class="json-editor" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="setDialog = false">取消</el-button>
        <el-button type="primary" @click="saveSet">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="caseDialog" :title="editingCase?.id ? '编辑用例' : '新增用例'" width="780px">
      <el-form label-position="top">
        <el-alert
          class="form-help"
          type="info"
          :closable="false"
          show-icon
          :title="currentCaseExample.title"
          :description="currentCaseExample.description"
        />
        <div class="toolbar compact-toolbar">
          <span>当前类型：{{ selected?.check_type }}</span>
          <el-button size="small" @click="applyCaseExample">套用当前类型示例</el-button>
        </div>
        <div class="grid-two">
          <el-form-item label="名称"><el-input v-model="caseForm.name" /></el-form-item>
          <el-form-item label="样本 ID"><el-input-number v-model="caseForm.sample_asset_id" :min="1" style="width: 100%" /></el-form-item>
        </div>
        <el-form-item label="输入配置 JSON">
          <el-input v-model="caseInputText" type="textarea" :rows="8" class="json-editor" />
        </el-form-item>
        <el-form-item label="期望配置 JSON">
          <el-input v-model="caseExpectedText" type="textarea" :rows="8" class="json-editor" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="caseDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCase">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="promptDialog" :title="editingPrompt?.id ? '编辑 Prompt' : '新增 Prompt'" width="780px">
      <el-form label-position="top">
        <div class="grid-two">
          <el-form-item label="名称"><el-input v-model="promptForm.name" /></el-form-item>
          <el-form-item label="版本"><el-input-number v-model="promptForm.version" :min="1" style="width: 100%" /></el-form-item>
        </div>
        <el-form-item label="启用"><el-switch v-model="promptForm.active" /></el-form-item>
        <el-form-item label="模板">
          <el-input v-model="promptForm.prompt_template" type="textarea" :rows="8" />
        </el-form-item>
        <el-form-item label="输出 Schema JSON">
          <el-input v-model="promptSchemaText" type="textarea" :rows="6" class="json-editor" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="promptDialog = false">取消</el-button>
        <el-button type="primary" @click="savePrompt">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';
import {
  api,
  parseJsonObject,
  statusType,
  type CheckType,
  type EvaluatorPrompt,
  type GoldenCase,
  type GoldenRun,
  type GoldenSet,
  type NewApiInstance
} from '../api';

const sets = ref<GoldenSet[]>([]);
const instances = ref<NewApiInstance[]>([]);
const prompts = ref<EvaluatorPrompt[]>([]);
const detail = ref<GoldenSet | null>(null);
const selected = ref<GoldenSet | null>(null);
const runs = ref<GoldenRun[]>([]);
const runningSetId = ref<number | null>(null);

const setDialog = ref(false);
const caseDialog = ref(false);
const promptDialog = ref(false);
const editingSet = ref<GoldenSet | null>(null);
const editingCase = ref<GoldenCase | null>(null);
const editingPrompt = ref<EvaluatorPrompt | null>(null);

const checkTypeOptions: Array<{ label: string; value: CheckType }> = [
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
  { label: '服务健康接口', value: 'http_health' },
  { label: '业务接口 + AI', value: 'http_content_ai' }
];

type CaseExample = {
  title: string;
  description: string;
  input_config: Record<string, unknown>;
  expected_config: Record<string, unknown>;
};

const caseExamples: Record<CheckType, CaseExample> = {
  model_llm_chat: {
    title: 'LLM Chat',
    description: '发送固定 prompt，要求模型稳定返回可解析 JSON，适合基础质量冒烟。',
    input_config: { prompt: 'Return JSON only: {"status":"ok","task":"golden"}', payload: { temperature: 0, max_tokens: 80 } },
    expected_config: { json_path: '$.status', json_path_equals: 'ok', ai_expectation: '输出必须是合法 JSON，并明确表示本次 golden 用例成功。' }
  },
  model_llm_completion: {
    title: 'LLM Completion',
    description: '用于仍兼容 /v1/completions 的模型，建议输出短文本或 JSON。',
    input_config: { prompt: 'Return JSON only: {"status":"ok"}', payload: { temperature: 0, max_tokens: 80 } },
    expected_config: { contains: 'ok', ai_expectation: '输出必须表示任务成功，不能是错误、拒答或无关文本。' }
  },
  model_vision_chat: {
    title: 'Vision 图像理解',
    description: '发送固定测试图片，校验图像理解输出是否描述了目标内容。',
    input_config: {
      prompt: 'Describe this image in one short word.',
      image_url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lV9m6wAAAABJRU5ErkJggg=='
    },
    expected_config: { ai_expectation: '输出必须是对图片内容的简短描述，不能为空或报告接口错误。' }
  },
  model_embedding: {
    title: 'Embedding 模型',
    description: '校验向量接口返回稳定结构；后端已检查非空向量，Golden Case 可再检查响应摘要。',
    input_config: { input: 'health check golden sample' },
    expected_config: { contains: 'embedding', ai_expectation: '响应摘要应表示已生成非空向量。' }
  },
  model_rerank: {
    title: 'Rerank 重排序',
    description: '用固定 query 和 documents 校验重排序接口有结果。',
    input_config: { endpoint: '/v1/rerank', query: 'healthy service', documents: ['service is healthy', 'service is down'] },
    expected_config: { contains: 'results', ai_expectation: '响应应包含可用的重排序结果。' }
  },
  model_audio_transcription: {
    title: '语音转文字 ASR',
    description: '可绑定样本 ID，或在输入配置里指定 file_path；适合音频解析质量回归。',
    input_config: { response_format: 'json', language: 'zh', require_text: true },
    expected_config: { json_path: '$.text', regex: '.+', ai_expectation: '转写文本应符合样本音频内容，不能为空或明显无关。' }
  },
  model_audio_translation: {
    title: '语音翻译',
    description: '可绑定样本 ID，校验翻译文本是否符合预期语言和含义。',
    input_config: { response_format: 'json', require_text: true },
    expected_config: { json_path: '$.text', regex: '.+', ai_expectation: '翻译文本必须表达样本音频的核心含义。' }
  },
  model_audio_speech: {
    title: '文字转语音 TTS',
    description: '发送固定文本，后端会检查返回非空音频二进制。',
    input_config: { input: 'health check', voice: 'alloy' },
    expected_config: { ai_expectation: '响应摘要应表示已生成非空语音音频。' }
  },
  model_image_generation: {
    title: '文生图',
    description: '发送固定绘图 prompt，后端检查返回图片 URL 或 base64。',
    input_config: { prompt: 'A simple green circle icon on a white background', size: '512x512' },
    expected_config: { contains: 'data', ai_expectation: '响应应包含成功生成的图片引用或 base64。' }
  },
  model_image_edit: {
    title: '图像编辑',
    description: '使用内置测试图片或绑定样本图片，后端检查返回编辑后的图片。',
    input_config: { prompt: 'Make the image brighter', size: '512x512' },
    expected_config: { contains: 'data', ai_expectation: '响应应包含成功编辑后的图片引用或 base64。' }
  },
  model_moderation: {
    title: '内容安全 Moderation',
    description: '发送固定安全文本，校验分类接口返回 results。',
    input_config: { input: 'This is a harmless health check message.' },
    expected_config: { contains: 'results', ai_expectation: '响应应包含内容安全分类结果。' }
  },
  model_custom_http: {
    title: '自定义模型 HTTP',
    description: '用于音频解析、结构化抽取、报告生成等非标准接口，重点用 JSONPath/Schema 校验结构。',
    input_config: { method: 'POST', url: 'http://127.0.0.1:9000/audio/parse', body_type: 'json', json_body: { sample_id: 'demo' } },
    expected_config: { expected_status_codes: [200], json_path: '$.code', json_path_equals: 0, ai_expectation: '响应必须包含有效结构化解析结果。' }
  },
  http_health: {
    title: '服务健康接口',
    description: '用于把普通健康接口纳入 Golden 回归，模型名可填服务名。',
    input_config: { method: 'GET', url: 'http://127.0.0.1:8080/healthz' },
    expected_config: { expected_status_codes: [200], json_path: '$.status', json_path_equals: 'ok' }
  },
  http_content_ai: {
    title: '业务接口 + AI',
    description: '先做状态码和结构规则校验，再用 ai_expectation 做语义兜底。',
    input_config: { method: 'POST', url: 'http://127.0.0.1:8080/api/report', body_type: 'json', json_body: { user_id: 'demo-user', range: 'today' } },
    expected_config: { expected_status_codes: [200], max_latency_ms: 3000, ai_expectation: '响应必须包含有效报告内容，不能是空结果、错误页或无关文本。' }
  }
};

const setForm = reactive({
  name: '',
  description: '',
  new_api_instance_id: null as number | null,
  model_name: '',
  check_type: 'model_llm_chat' as CheckType,
  enabled: true,
  evaluator_prompt_id: null as number | null
});
const setEvaluatorText = ref(JSON.stringify({ min_confidence: 0.7, always_ai: false }, null, 2));
const caseForm = reactive({ name: '', enabled: true, sample_asset_id: null as number | null });
const caseInputText = ref(JSON.stringify({ prompt: 'Return JSON: {"status":"ok"}' }, null, 2));
const caseExpectedText = ref(JSON.stringify({ contains: 'ok', ai_expectation: '输出表示状态正常' }, null, 2));
const promptForm = reactive({ name: 'default', version: 1, active: true, prompt_template: '' });
const promptSchemaText = ref('{}');
const currentCaseExample = computed(() => caseExamples[selected.value?.check_type ?? setForm.check_type]);

async function load() {
  const [setRows, promptRows, instanceRows] = await Promise.all([api.goldenSets(), api.evaluatorPrompts(), api.instances()]);
  sets.value = setRows;
  prompts.value = promptRows;
  instances.value = instanceRows;
}

async function selectSet(row: GoldenSet) {
  selected.value = row;
  detail.value = await api.goldenSet(row.id);
  await loadRuns();
}

async function loadRuns() {
  if (selected.value) runs.value = await api.goldenRuns(selected.value.id);
}

function openSetCreate() {
  editingSet.value = null;
  Object.assign(setForm, {
    name: '',
    description: '',
    new_api_instance_id: instances.value.find((item) => item.is_default)?.id ?? null,
    model_name: '',
    check_type: 'model_llm_chat',
    enabled: true,
    evaluator_prompt_id: null
  });
  setEvaluatorText.value = JSON.stringify({ min_confidence: 0.7, always_ai: false }, null, 2);
  setDialog.value = true;
}

function instanceName(id?: number | null) {
  if (!id) return '默认';
  return instances.value.find((item) => item.id === id)?.name ?? `#${id}`;
}

function openSetEdit(row: GoldenSet) {
  editingSet.value = row;
  Object.assign(setForm, row);
  setEvaluatorText.value = JSON.stringify(row.evaluator_config ?? {}, null, 2);
  setDialog.value = true;
}

async function saveSet() {
  const payload = { ...setForm, evaluator_config: parseJsonObject(setEvaluatorText.value) };
  if (editingSet.value) await api.updateGoldenSet(editingSet.value.id, payload);
  else await api.createGoldenSet(payload);
  setDialog.value = false;
  ElMessage.success('集合已保存');
  await load();
}

async function removeSet(row: GoldenSet) {
  await ElMessageBox.confirm(`删除集合「${row.name}」？`, '确认删除', { type: 'warning' });
  await api.deleteGoldenSet(row.id);
  if (selected.value?.id === row.id) selected.value = null;
  await load();
}

function openCaseCreate() {
  editingCase.value = null;
  Object.assign(caseForm, { name: '', enabled: true, sample_asset_id: null });
  applyCaseExample();
  caseDialog.value = true;
}

function applyCaseExample() {
  const example = currentCaseExample.value;
  caseInputText.value = JSON.stringify(example.input_config, null, 2);
  caseExpectedText.value = JSON.stringify(example.expected_config, null, 2);
  if (!caseForm.name) caseForm.name = example.title;
}

function openCaseEdit(row: GoldenCase) {
  editingCase.value = row;
  Object.assign(caseForm, row);
  caseInputText.value = JSON.stringify(row.input_config ?? {}, null, 2);
  caseExpectedText.value = JSON.stringify(row.expected_config ?? {}, null, 2);
  caseDialog.value = true;
}

async function saveCase() {
  if (!selected.value) return;
  const payload = {
    ...caseForm,
    input_config: parseJsonObject(caseInputText.value),
    expected_config: parseJsonObject(caseExpectedText.value)
  };
  if (editingCase.value) await api.updateGoldenCase(selected.value.id, editingCase.value.id, payload);
  else await api.createGoldenCase(selected.value.id, payload);
  caseDialog.value = false;
  ElMessage.success('用例已保存');
  await selectSet(selected.value);
}

async function removeCase(row: GoldenCase) {
  if (!selected.value) return;
  await api.deleteGoldenCase(selected.value.id, row.id);
  await selectSet(selected.value);
}

async function runSet(row: GoldenSet) {
  runningSetId.value = row.id;
  try {
    await api.runGoldenSet(row.id);
    ElMessage.success('回归运行完成');
    await selectSet(row);
  } finally {
    runningSetId.value = null;
  }
}

function openPromptCreate() {
  editingPrompt.value = null;
  Object.assign(promptForm, {
    name: 'default',
    version: 1,
    active: true,
    prompt_template:
      'You are a strict monitoring evaluator. Return JSON only: {"passed": boolean, "confidence": number, "score": number, "reason": string}.\\nExpectation: {expectation}\\nObserved output: {response_text}'
  });
  promptSchemaText.value = JSON.stringify({ required: ['passed', 'confidence', 'score', 'reason'] }, null, 2);
  promptDialog.value = true;
}

function openPromptEdit(row: EvaluatorPrompt) {
  editingPrompt.value = row;
  Object.assign(promptForm, row);
  promptSchemaText.value = JSON.stringify(row.output_schema ?? {}, null, 2);
  promptDialog.value = true;
}

async function savePrompt() {
  const payload = { ...promptForm, output_schema: parseJsonObject(promptSchemaText.value) };
  if (editingPrompt.value) await api.updateEvaluatorPrompt(editingPrompt.value.id, payload);
  else await api.createEvaluatorPrompt(payload);
  promptDialog.value = false;
  ElMessage.success('Prompt 已保存');
  await load();
}

onMounted(load);
</script>
