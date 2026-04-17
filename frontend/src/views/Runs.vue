<template>
  <section class="section">
    <div class="toolbar">
      <strong>运行记录</strong>
      <div class="filter-bar">
        <el-input-number v-model="filters.check_id" :min="1" placeholder="检查 ID" />
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px">
          <el-option label="success" value="success" />
          <el-option label="failure" value="failure" />
        </el-select>
        <el-select v-model="filters.run_mode" clearable placeholder="模式" style="width: 140px">
          <el-option label="测试运行" value="test" />
          <el-option label="正式运行" value="manual" />
          <el-option label="调度运行" value="scheduled" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
      </div>
    </div>
    <el-alert
      class="form-help"
      type="info"
      :closable="false"
      show-icon
      title="运行模式说明"
      description="test 是测试运行，不触发告警；manual 是手动正式运行；scheduled 是调度器按间隔自动执行。"
    />
    <el-table :data="runs" stripe>
      <el-table-column prop="id" label="Run ID" width="90" />
      <el-table-column prop="check_id" label="检查 ID" width="100" />
      <el-table-column prop="run_mode" label="模式" width="100" />
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
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { api, statusType, type CheckRun } from '../api';

const runs = ref<CheckRun[]>([]);
const filters = reactive<{ check_id: number | null; status: string; run_mode: string }>({
  check_id: null,
  status: '',
  run_mode: ''
});
const pagination = reactive({ page: 1, page_size: 20, total: 0 });

async function load() {
  const page = await api.allRuns({
    check_id: filters.check_id,
    status: filters.status,
    run_mode: filters.run_mode,
    page: pagination.page,
    page_size: pagination.page_size
  });
  runs.value = page.items;
  pagination.total = page.total;
}

onMounted(load);
</script>
