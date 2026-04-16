<template>
  <div>
    <div class="metrics">
      <div class="metric">
        <div class="metric-label">整体可用率</div>
        <div class="metric-value">{{ summary?.availability ?? 0 }}%</div>
      </div>
      <div class="metric">
        <div class="metric-label">启用检查</div>
        <div class="metric-value">{{ summary?.enabled_checks ?? 0 }}</div>
      </div>
      <div class="metric">
        <div class="metric-label">失败检查</div>
        <div class="metric-value">{{ summary?.failing_checks ?? 0 }}</div>
      </div>
      <div class="metric">
        <div class="metric-label">未匹配模型</div>
        <div class="metric-value">{{ summary?.model_unmatched ?? 0 }}</div>
      </div>
    </div>

    <div class="grid-two">
      <section class="section">
        <div class="toolbar">
          <strong>最近运行</strong>
          <el-button size="small" @click="load">刷新</el-button>
        </div>
        <el-table :data="summary?.recent_runs ?? []" stripe>
          <el-table-column prop="id" label="Run ID" width="90" />
          <el-table-column prop="check_id" label="检查 ID" width="90" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="duration_ms" label="耗时 ms" width="110" />
          <el-table-column prop="error" label="错误" show-overflow-tooltip />
        </el-table>
      </section>

      <section class="section">
        <div class="toolbar">
          <strong>最近告警</strong>
        </div>
        <el-table :data="summary?.recent_alerts ?? []" stripe>
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="event_type" label="类型" width="100" />
          <el-table-column prop="status" label="发送状态" width="110" />
          <el-table-column prop="error" label="错误" show-overflow-tooltip />
        </el-table>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api, type DashboardSummary, statusType } from '../api';

const summary = ref<DashboardSummary | null>(null);

async function load() {
  summary.value = await api.summary();
}

onMounted(load);
</script>

