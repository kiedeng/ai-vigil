<template>
  <section class="section">
    <div class="toolbar">
      <strong>系统设置</strong>
      <el-button type="primary" @click="save">保存</el-button>
    </div>
    <el-form label-position="top" style="max-width: 760px">
      <el-form-item label="AI 校验模型">
        <el-input v-model="form.evaluator_model" />
      </el-form-item>
      <div class="grid-two">
        <el-form-item label="默认检查间隔秒">
          <el-input-number v-model="form.default_interval_seconds" :min="10" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认超时秒">
          <el-input-number v-model="form.default_timeout_seconds" :min="1" style="width: 100%" />
        </el-form-item>
      </div>
      <div class="grid-two">
        <el-form-item label="默认连续失败阈值">
          <el-input-number v-model="form.default_failure_threshold" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认告警冷却分钟">
          <el-input-number v-model="form.alert_cooldown_minutes" :min="1" style="width: 100%" />
        </el-form-item>
      </div>
      <div class="grid-two">
        <el-form-item label="每日巡检报告">
          <el-switch v-model="form.daily_report_enabled" />
        </el-form-item>
        <el-form-item label="报告发送时间">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input-number v-model="form.daily_report_hour" :min="0" :max="23" style="width: 100%" />
            <el-input-number v-model="form.daily_report_minute" :min="0" :max="59" style="width: 100%" />
          </div>
        </el-form-item>
      </div>
      <el-form-item label="数据库连接">
        <el-input v-model="databaseUrl" disabled />
      </el-form-item>
      <el-alert title="new-api 实例和密钥请在模型中心维护；日报按 Asia/Shanghai 时间发送。" type="info" :closable="false" />

      <el-divider content-position="left">配置文件导入</el-divider>
      <el-form-item label="YAML 配置文件">
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
          <el-input v-model="importPath" placeholder="ai-vigil.yaml（默认）" style="width: 280px" />
          <el-button type="primary" :loading="importing" @click="doImport">导入配置文件</el-button>
          <el-button @click="downloadTemplate">下载模板</el-button>
        </div>
        <div style="margin-top: 8px; color: #909399; font-size: 12px">
          从 YAML 文件导入 instances、checks、alert_channels、golden_sets。按 name upsert，不删除已有数据。
        </div>
      </el-form-item>
      <el-alert
        v-if="importResult"
        :title="importResult.success ? '导入成功' : '导入完成（有错误）'"
        :type="importResult.success ? 'success' : 'warning'"
        :closable="true"
        show-icon
        style="margin-bottom: 16px"
      >
        <template #default>
          <pre style="margin: 4px 0 0; font-size: 12px; white-space: pre-wrap">{{ importResult.message }}</pre>
          <ul v-if="importResult.errors && Object.values(importResult.errors).some(v => v?.length)" style="margin: 4px 0 0; font-size: 12px">
            <li v-for="(errs, section) in importResult.errors" :key="String(section)">
              <template v-if="errs?.length">
                <strong>{{ section }}</strong>: <span v-for="e in errs" :key="e">{{ e }}；</span>
              </template>
            </li>
          </ul>
        </template>
      </el-alert>
    </el-form>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { api } from '../api';

const databaseUrl = ref('');
const importing = ref(false);
const importPath = ref('');
const importResult = ref<{
  success: boolean;
  message: string;
  errors: Record<string, string[]>;
} | null>(null);
const form = reactive({
  evaluator_model: '',
  default_interval_seconds: 300,
  default_timeout_seconds: 120,
  default_failure_threshold: 3,
  alert_cooldown_minutes: 30,
  daily_report_enabled: true,
  daily_report_hour: 9,
  daily_report_minute: 0
});

async function load() {
  const settings = await api.settings();
  Object.assign(form, {
    evaluator_model: settings.evaluator_model,
    default_interval_seconds: settings.default_interval_seconds,
    default_timeout_seconds: settings.default_timeout_seconds,
    default_failure_threshold: settings.default_failure_threshold,
    alert_cooldown_minutes: settings.alert_cooldown_minutes,
    daily_report_enabled: settings.daily_report_enabled,
    daily_report_hour: settings.daily_report_hour,
    daily_report_minute: settings.daily_report_minute
  });
  databaseUrl.value = String(settings.database_url ?? '');
}

async function save() {
  await api.updateSettings(form);
  ElMessage.success('设置已保存');
  await load();
}

async function doImport() {
  importing.value = true;
  importResult.value = null;
  try {
    const result = await api.importConfig(importPath.value || undefined);
    importResult.value = result;
  } catch (e: unknown) {
    importResult.value = {
      success: false,
      message: (e as Error).message || String(e),
      errors: {},
    };
  } finally {
    importing.value = false;
  }
}

function downloadTemplate() {
  const link = document.createElement('a');
  link.href = '/ai-vigil.yaml.example';
  link.download = 'ai-vigil.yaml.example';
  link.click();
}

onMounted(load);
</script>
