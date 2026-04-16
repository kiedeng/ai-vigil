<template>
  <section class="section">
    <div class="toolbar">
      <strong>运行记录</strong>
      <div style="display: flex; gap: 10px; flex-wrap: wrap">
        <el-input-number v-model="filters.check_id" :min="1" placeholder="检查 ID" />
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px">
          <el-option label="success" value="success" />
          <el-option label="failure" value="failure" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
      </div>
    </div>
    <el-table :data="runs" stripe>
      <el-table-column prop="id" label="Run ID" width="90" />
      <el-table-column prop="check_id" label="检查 ID" width="100" />
      <el-table-column prop="created_at" label="时间" width="190" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="response_status_code" label="HTTP" width="90" />
      <el-table-column prop="duration_ms" label="耗时 ms" width="100" />
      <el-table-column prop="error" label="错误" min-width="220" show-overflow-tooltip />
      <el-table-column prop="response_summary" label="响应摘要" min-width="260" show-overflow-tooltip />
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { api, statusType, type CheckRun } from '../api';

const runs = ref<CheckRun[]>([]);
const filters = reactive<{ check_id: number | null; status: string }>({
  check_id: null,
  status: ''
});

async function load() {
  runs.value = await api.allRuns({ check_id: filters.check_id, status: filters.status, limit: 200 });
}

onMounted(load);
</script>

