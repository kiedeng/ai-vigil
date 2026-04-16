<template>
  <section class="section">
    <div class="toolbar">
      <strong>检查样本</strong>
      <div style="display: flex; gap: 10px; flex-wrap: wrap">
        <el-input v-model="logicalName" placeholder="样本名称，如 asr-zh" style="width: 220px" />
        <el-input v-model="description" placeholder="描述" style="width: 220px" />
        <input ref="fileInput" type="file" @change="onFileChange" />
        <el-button type="primary" :disabled="!selectedFile || !logicalName" @click="upload">上传新版本</el-button>
      </div>
    </div>
    <el-table :data="samples" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="logical_name" label="样本名" min-width="160" />
      <el-table-column prop="version" label="版本" width="90" />
      <el-table-column prop="filename" label="文件名" min-width="180" show-overflow-tooltip />
      <el-table-column prop="content_type" label="类型" min-width="140" />
      <el-table-column prop="size_bytes" label="大小" width="110" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="预览" width="100">
        <template #default="{ row }">
          <el-button size="small" @click="preview(row)">打开</el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { onMounted, ref } from 'vue';
import { api, type SampleAsset } from '../api';

const samples = ref<SampleAsset[]>([]);
const logicalName = ref('');
const description = ref('');
const selectedFile = ref<File | null>(null);

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] ?? null;
}

async function load() {
  samples.value = await api.samples();
}

async function upload() {
  if (!selectedFile.value) return;
  await api.uploadSample({
    file: selectedFile.value,
    logical_name: logicalName.value,
    description: description.value
  });
  ElMessage.success('样本已上传');
  selectedFile.value = null;
  await load();
}

async function preview(row: SampleAsset) {
  const token = localStorage.getItem('ai-eye-token');
  const response = await fetch(`/api/samples/${row.id}/content`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!response.ok) {
    ElMessage.error('样本预览失败');
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
}

onMounted(load);
</script>
