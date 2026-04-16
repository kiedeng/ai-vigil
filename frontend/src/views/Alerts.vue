<template>
  <section class="section">
    <div class="toolbar">
      <strong>Webhook 通道</strong>
      <div>
        <el-button @click="testDaily">发送测试日报</el-button>
        <el-button type="primary" @click="openCreate">新增通道</el-button>
      </div>
    </div>
    <el-table :data="channels" stripe>
      <el-table-column prop="id" label="ID" width="72" />
      <el-table-column prop="name" label="名称" min-width="160" />
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

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑通道' : '新增通道'" width="680px">
      <el-form label-position="top">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="Webhook URL">
          <el-input v-model="form.webhook_url" />
        </el-form-item>
        <div class="grid-two">
          <el-form-item label="冷却分钟">
            <el-input-number v-model="form.cooldown_minutes" :min="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="form.enabled" />
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
import { api, parseJsonObject, type AlertChannel } from '../api';

const channels = ref<AlertChannel[]>([]);
const dialogVisible = ref(false);
const editing = ref<AlertChannel | null>(null);
const headersText = ref('{}');
const form = reactive({
  name: '',
  enabled: true,
  webhook_url: '',
  secret: '',
  cooldown_minutes: 30
});

async function load() {
  channels.value = await api.channels();
}

function openCreate() {
  editing.value = null;
  Object.assign(form, { name: '', enabled: true, webhook_url: '', secret: '', cooldown_minutes: 30 });
  headersText.value = '{}';
  dialogVisible.value = true;
}

function openEdit(row: AlertChannel) {
  editing.value = row;
  Object.assign(form, row);
  headersText.value = JSON.stringify(row.headers ?? {}, null, 2);
  dialogVisible.value = true;
}

async function save() {
  const payload = { ...form, headers: parseJsonObject(headersText.value), secret: form.secret || null };
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
  await api.testChannel(row.id);
  ElMessage.success('测试告警已发送');
}

async function testDaily() {
  await api.testDailyReport();
  ElMessage.success('测试日报已发送');
}

async function remove(row: AlertChannel) {
  await ElMessageBox.confirm(`删除通道「${row.name}」？`, '确认删除', { type: 'warning' });
  await api.deleteChannel(row.id);
  ElMessage.success('通道已删除');
  await load();
}

onMounted(load);
</script>
