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
    </el-form>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { api } from '../api';

const databaseUrl = ref('');
const form = reactive({
  evaluator_model: '',
  default_interval_seconds: 300,
  default_timeout_seconds: 30,
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

onMounted(load);
</script>
