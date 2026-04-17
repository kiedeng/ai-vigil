<template>
  <section class="section">
    <div class="toolbar">
      <strong>Webhook 通道</strong>
      <div>
        <el-button @click="testDaily">发送测试日报</el-button>
        <el-button type="primary" @click="openCreate">新增通道</el-button>
      </div>
    </div>

    <el-alert
      class="wecom-help"
      type="info"
      :closable="false"
      show-icon
      title="企业微信机器人请选择“企业微信 Markdown”，Webhook URL 填完整机器人地址，Headers 保持 {}，Secret 留空；HTTPS 证书异常时可配置 CA bundle，必要时仅对该通道关闭 SSL 校验。"
    />

    <el-table :data="channels" stripe>
      <el-table-column prop="id" label="ID" width="72" />
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column label="类型" width="150">
        <template #default="{ row }">
          {{ channelTypeLabel(row.channel_type) }}
        </template>
      </el-table-column>
      <el-table-column prop="webhook_url" label="Webhook" min-width="260" show-overflow-tooltip />
      <el-table-column prop="cooldown_minutes" label="冷却分钟" width="110" />
      <el-table-column label="启用" width="90">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="toggle(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="test(row)">测试</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="toolbar logs-toolbar">
      <strong>发送日志</strong>
      <div class="filter-bar">
        <el-select v-model="eventFilters.status" clearable placeholder="状态" style="width: 120px">
          <el-option label="sent" value="sent" />
          <el-option label="failed" value="failed" />
        </el-select>
        <el-select v-model="eventFilters.event_type" clearable placeholder="事件" style="width: 150px">
          <el-option label="test" value="test" />
          <el-option label="daily_report" value="daily_report" />
          <el-option label="failure" value="failure" />
          <el-option label="recovery" value="recovery" />
        </el-select>
        <el-button @click="loadEvents">刷新</el-button>
      </div>
    </div>
    <el-table :data="events" stripe>
      <el-table-column prop="created_at" label="时间" min-width="180">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="channel_id" label="通道" width="90" />
      <el-table-column prop="event_type" label="事件" width="130" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'sent' ? 'success' : 'danger'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="错误" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.error || '-' }}
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      class="pager"
      layout="total, sizes, prev, pager, next"
      :total="eventPagination.total"
      v-model:current-page="eventPagination.page"
      v-model:page-size="eventPagination.page_size"
      :page-sizes="[20, 50, 100]"
      @current-change="loadEvents"
      @size-change="loadEvents"
    />

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑通道' : '新增通道'" width="680px">
      <el-form label-position="top">
        <div class="grid-two">
          <el-form-item label="名称">
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item label="通道类型">
            <el-select v-model="form.channel_type" style="width: 100%">
              <el-option label="通用 Webhook" value="generic" />
              <el-option label="企业微信 Markdown" value="wecom_markdown" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="Webhook URL">
          <el-input v-model="form.webhook_url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
        </el-form-item>
        <el-alert
          v-if="form.channel_type === 'wecom_markdown'"
          class="form-help"
          type="success"
          :closable="false"
          title="企业微信机器人会收到 Markdown 消息；Headers 保持 {}，Secret 留空即可。"
        />
        <div class="grid-two">
          <el-form-item label="冷却分钟">
            <el-input-number v-model="form.cooldown_minutes" :min="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="form.enabled" />
          </el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item label="校验 HTTPS 证书">
            <el-switch v-model="form.verify_ssl" />
          </el-form-item>
          <el-form-item label="CA bundle 路径">
            <el-input v-model="form.ca_bundle_path" placeholder="/etc/ssl/certs/ca-certificates.crt" />
          </el-form-item>
        </div>
        <el-form-item label="签名 Secret">
          <el-input v-model="form.secret" type="password" show-password />
        </el-form-item>
        <el-form-item label="Headers JSON">
          <el-input v-model="headersText" type="textarea" :rows="6" class="json-editor" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { api, parseJsonObject, type AlertChannel, type AlertEvent } from '../api';

type AlertChannelType = AlertChannel['channel_type'];

const channels = ref<AlertChannel[]>([]);
const events = ref<AlertEvent[]>([]);
const dialogVisible = ref(false);
const editing = ref<AlertChannel | null>(null);
const headersText = ref('{}');
const form = reactive({
  name: '',
  channel_type: 'generic' as AlertChannelType,
  enabled: true,
  webhook_url: '',
  secret: '',
  cooldown_minutes: 30,
  verify_ssl: true,
  ca_bundle_path: ''
});
const eventFilters = reactive({ status: '', event_type: '' });
const eventPagination = reactive({ page: 1, page_size: 20, total: 0 });

async function load() {
  channels.value = await api.channels();
}

async function loadEvents() {
  const page = await api.alertEvents({
    status: eventFilters.status,
    event_type: eventFilters.event_type,
    page: eventPagination.page,
    page_size: eventPagination.page_size
  });
  events.value = page.items;
  eventPagination.total = page.total;
}

function channelTypeLabel(type: AlertChannelType) {
  return type === 'wecom_markdown' ? '企业微信 Markdown' : '通用 Webhook';
}

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

function openCreate() {
  editing.value = null;
  Object.assign(form, {
    name: '',
    channel_type: 'wecom_markdown',
    enabled: true,
    webhook_url: '',
    secret: '',
    cooldown_minutes: 30,
    verify_ssl: true,
    ca_bundle_path: ''
  });
  headersText.value = '{}';
  dialogVisible.value = true;
}

function openEdit(row: AlertChannel) {
  editing.value = row;
  Object.assign(form, {
    name: row.name,
    channel_type: row.channel_type,
    enabled: row.enabled,
    webhook_url: row.webhook_url,
    secret: row.secret ?? '',
    cooldown_minutes: row.cooldown_minutes,
    verify_ssl: row.verify_ssl,
    ca_bundle_path: row.ca_bundle_path ?? ''
  });
  headersText.value = JSON.stringify(row.headers ?? {}, null, 2);
  dialogVisible.value = true;
}

async function save() {
  const payload = {
    ...form,
    headers: parseJsonObject(headersText.value),
    secret: form.secret || null,
    ca_bundle_path: form.ca_bundle_path || null
  };
  if (editing.value) {
    await api.updateChannel(editing.value.id, payload);
  } else {
    await api.createChannel(payload);
  }
  dialogVisible.value = false;
  ElMessage.success('通道已保存');
  await load();
}

async function toggle(row: AlertChannel) {
  await api.updateChannel(row.id, { enabled: row.enabled });
}

async function test(row: AlertChannel) {
  const event = await api.testChannel(row.id);
  await loadEvents();
  if (event.status === 'sent') {
    ElMessage.success('测试消息已发送');
    return;
  }
  ElMessage.error(event.error || '测试消息发送失败');
}

async function testDaily() {
  const sentEvents = await api.testDailyReport();
  await loadEvents();
  if (!sentEvents.length) {
    ElMessage.warning('没有启用的告警通道，测试日报未发送');
    return;
  }
  const failed = sentEvents.find((event) => event.status !== 'sent');
  if (failed) {
    ElMessage.error(failed.error || '测试日报发送失败');
    return;
  }
  ElMessage.success('测试日报已发送');
}

async function remove(row: AlertChannel) {
  await ElMessageBox.confirm(`删除通道「${row.name}」？`, '确认删除', { type: 'warning' });
  await api.deleteChannel(row.id);
  ElMessage.success('通道已删除');
  await load();
  await loadEvents();
}

onMounted(async () => {
  await load();
  await loadEvents();
});
</script>

<style scoped>
.wecom-help,
.form-help,
.logs-toolbar {
  margin-top: 16px;
}
</style>
