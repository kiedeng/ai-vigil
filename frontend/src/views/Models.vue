<template>
  <div>
    <section class="section">
      <div class="toolbar">
        <strong>new-api 实例</strong>
        <el-button type="primary" @click="openInstanceCreate">新增实例</el-button>
      </div>
      <el-alert
        class="form-help"
        type="info"
        :closable="false"
        show-icon
        title="使用提示"
        description="实例代表一个 new-api 网关，例如测试环境和生产环境；模型同步会读取 /v1/models，分类规则命中后可自动创建检查项。"
      />
      <el-table :data="instances" stripe>
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="base_url" label="Base URL" min-width="240" show-overflow-tooltip />
        <el-table-column label="Key" width="90">
          <template #default="{ row }">{{ row.api_key_configured ? '已配置' : '未配置' }}</template>
        </el-table-column>
        <el-table-column label="默认" width="90">
          <template #default="{ row }"><el-tag v-if="row.is_default" type="success">默认</el-tag></template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="updateInstance(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="290" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="testInstance(row)">测试</el-button>
            <el-button size="small" :disabled="row.is_default" @click="makeDefault(row)">设默认</el-button>
            <el-button size="small" @click="openInstanceEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeInstance(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="section">
      <div class="toolbar">
        <strong>new-api 模型</strong>
        <div style="display: flex; gap: 8px; flex-wrap: wrap">
          <el-select v-model="selectedInstanceId" clearable placeholder="全部实例" style="width: 180px" @change="loadModels">
            <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
          <el-input v-model="modelSearch" clearable placeholder="搜索模型 ID" style="width: 180px" @keyup.enter="loadModels" />
          <el-button :loading="syncing" @click="syncSelected">同步当前实例</el-button>
          <el-button type="primary" :loading="syncing" @click="syncAll">同步全部</el-button>
        </div>
      </div>
      <el-table :data="models" stripe>
        <el-table-column prop="instance_name" label="实例" width="140" />
        <el-table-column prop="model_id" label="模型 ID" min-width="220" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="check_type" label="检查类型" width="180" />
        <el-table-column prop="matched_rule_id" label="规则 ID" width="100" />
        <el-table-column prop="check_id" label="检查 ID" width="100" />
        <el-table-column prop="last_seen_at" label="最后发现" width="190" />
      </el-table>
      <el-pagination
        class="pager"
        layout="total, sizes, prev, pager, next"
        :total="modelPagination.total"
        v-model:current-page="modelPagination.page"
        v-model:page-size="modelPagination.page_size"
        :page-sizes="[20, 50, 100]"
        @current-change="loadModels"
        @size-change="loadModels"
      />
    </section>

    <el-dialog v-model="instanceDialogVisible" :title="editingInstance?.id ? '编辑实例' : '新增实例'" width="680px">
      <el-form label-position="top">
        <div class="grid-two">
          <el-form-item label="名称">
            <el-input v-model="instanceForm.name" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="instanceForm.enabled" />
          </el-form-item>
        </div>
        <el-form-item label="Base URL">
          <el-input v-model="instanceForm.base_url" placeholder="http://127.0.0.1:3000" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="instanceForm.api_key" type="password" show-password placeholder="留空表示清除密钥" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="instanceForm.description" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="instanceForm.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="instanceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveInstance">保存</el-button>
      </template>
    </el-dialog>

    <section class="section">
      <div class="toolbar">
        <strong>分类规则</strong>
        <el-button @click="openCreate">新增规则</el-button>
      </div>
      <el-table :data="rules" stripe>
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="pattern" label="模式" min-width="180" />
        <el-table-column prop="match_type" label="匹配" width="100" />
        <el-table-column prop="check_type" label="检查类型" width="180" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="updateRule(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑规则' : '新增规则'" width="720px">
      <el-form label-position="top">
        <div class="grid-two">
          <el-form-item label="名称">
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="form.priority" style="width: 100%" />
          </el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item label="匹配模式">
            <el-input v-model="form.pattern" placeholder="deepseek*" />
          </el-form-item>
          <el-form-item label="匹配类型">
            <el-select v-model="form.match_type" style="width: 100%">
              <el-option label="glob" value="glob" />
              <el-option label="regex" value="regex" />
              <el-option label="exact" value="exact" />
            </el-select>
          </el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item label="检查类型">
            <el-select v-model="form.check_type" style="width: 100%">
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
            </el-select>
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="form.enabled" />
          </el-form-item>
        </div>
        <el-form-item label="请求配置 JSON">
          <el-input v-model="requestConfigText" type="textarea" :rows="6" class="json-editor" />
        </el-form-item>
        <el-form-item label="校验配置 JSON">
          <el-input v-model="validationConfigText" type="textarea" :rows="6" class="json-editor" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { api, parseJsonObject, type CheckType, type ModelRule, type NewApiInstance, type NewApiModel } from '../api';

const instances = ref<NewApiInstance[]>([]);
const models = ref<NewApiModel[]>([]);
const rules = ref<ModelRule[]>([]);
const syncing = ref(false);
const selectedInstanceId = ref<number | null>(null);
const modelSearch = ref('');
const modelPagination = reactive({ page: 1, page_size: 20, total: 0 });
const instanceDialogVisible = ref(false);
const dialogVisible = ref(false);
const editingInstance = ref<NewApiInstance | null>(null);
const editing = ref<ModelRule | null>(null);
const requestConfigText = ref('{}');
const validationConfigText = ref('{}');

const form = reactive({
  name: '',
  pattern: '',
  match_type: 'glob' as 'glob' | 'regex' | 'exact',
  check_type: 'model_llm_chat' as CheckType,
  enabled: true,
  priority: 100
});
const instanceForm = reactive({
  name: '',
  base_url: '',
  api_key: '',
  enabled: true,
  is_default: false,
  description: ''
});

async function load() {
  const [instanceRows, ruleRows] = await Promise.all([api.instances(), api.rules()]);
  instances.value = instanceRows;
  rules.value = ruleRows;
  await loadModels();
}

async function loadModels() {
  const page = await api.models({
    instance_id: selectedInstanceId.value,
    search: modelSearch.value,
    page: modelPagination.page,
    page_size: modelPagination.page_size
  });
  models.value = page.items;
  modelPagination.total = page.total;
}

function openInstanceCreate() {
  editingInstance.value = null;
  Object.assign(instanceForm, { name: '', base_url: '', api_key: '', enabled: true, is_default: false, description: '' });
  instanceDialogVisible.value = true;
}

function openInstanceEdit(row: NewApiInstance) {
  editingInstance.value = row;
  Object.assign(instanceForm, { ...row, api_key: '' });
  instanceDialogVisible.value = true;
}

async function saveInstance() {
  const payload: Partial<NewApiInstance> & { api_key?: string | null } = { ...instanceForm };
  if (instanceForm.api_key) payload.api_key = instanceForm.api_key;
  else if (!editingInstance.value) payload.api_key = null;
  else delete payload.api_key;
  if (editingInstance.value) await api.updateInstance(editingInstance.value.id, payload);
  else await api.createInstance(payload);
  instanceDialogVisible.value = false;
  ElMessage.success('实例已保存');
  await load();
}

async function updateInstance(row: NewApiInstance) {
  await api.updateInstance(row.id, { enabled: row.enabled });
}

async function makeDefault(row: NewApiInstance) {
  await api.setDefaultInstance(row.id);
  ElMessage.success('默认实例已更新');
  await load();
}

async function testInstance(row: NewApiInstance) {
  await api.testInstance(row.id);
  ElMessage.success('实例连接正常');
}

async function removeInstance(row: NewApiInstance) {
  await ElMessageBox.confirm(`删除实例「${row.name}」？如果已有检查或模型绑定会被后端拒绝。`, '确认删除', { type: 'warning' });
  await api.deleteInstance(row.id);
  ElMessage.success('实例已删除');
  await load();
}

async function syncSelected() {
  syncing.value = true;
  try {
    await api.syncModels(selectedInstanceId.value);
    ElMessage.success('模型已同步');
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '同步失败');
  } finally {
    syncing.value = false;
  }
}

async function syncAll() {
  syncing.value = true;
  try {
    await api.syncAllModels();
    ElMessage.success('全部实例模型已同步');
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '同步失败');
  } finally {
    syncing.value = false;
  }
}

function openCreate() {
  editing.value = null;
  Object.assign(form, { name: '', pattern: '', match_type: 'glob', check_type: 'model_llm_chat', enabled: true, priority: 100 });
  requestConfigText.value = '{}';
  validationConfigText.value = '{}';
  dialogVisible.value = true;
}

function openEdit(row: ModelRule) {
  editing.value = row;
  Object.assign(form, row);
  requestConfigText.value = JSON.stringify(row.request_config ?? {}, null, 2);
  validationConfigText.value = JSON.stringify(row.validation_config ?? {}, null, 2);
  dialogVisible.value = true;
}

async function saveRule() {
  const payload = {
    ...form,
    request_config: parseJsonObject(requestConfigText.value),
    validation_config: parseJsonObject(validationConfigText.value)
  };
  if (editing.value) {
    await api.updateRule(editing.value.id, payload);
  } else {
    await api.createRule(payload);
  }
  dialogVisible.value = false;
  ElMessage.success('规则已保存');
  await load();
}

async function updateRule(row: ModelRule) {
  await api.updateRule(row.id, { enabled: row.enabled });
}

async function removeRule(row: ModelRule) {
  await ElMessageBox.confirm(`删除规则「${row.name}」？`, '确认删除', { type: 'warning' });
  await api.deleteRule(row.id);
  ElMessage.success('规则已删除');
  await load();
}

onMounted(load);
</script>
