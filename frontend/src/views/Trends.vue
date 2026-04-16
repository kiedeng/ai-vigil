<template>
  <div>
    <div class="metrics">
      <div v-for="bucket in buckets" :key="bucket.label" class="metric">
        <div class="metric-label">{{ bucket.label }} 可用率</div>
        <div class="metric-value">{{ bucket.availability }}%</div>
        <div class="metric-label">错误率 {{ bucket.error_rate }}% / 总数 {{ bucket.total }}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Golden Set 通过率</div>
        <div class="metric-value">{{ trends?.golden.pass_rate ?? 0 }}%</div>
        <div class="metric-label">总数 {{ trends?.golden.total ?? 0 }}</div>
      </div>
    </div>

    <section class="section">
      <div class="toolbar">
        <strong>延迟分位</strong>
        <el-button @click="load">刷新</el-button>
      </div>
      <el-table :data="buckets" stripe>
        <el-table-column prop="label" label="窗口" width="100" />
        <el-table-column prop="p50_ms" label="P50 ms" />
        <el-table-column prop="p90_ms" label="P90 ms" />
        <el-table-column prop="p95_ms" label="P95 ms" />
        <el-table-column prop="p99_ms" label="P99 ms" />
        <el-table-column prop="failure" label="失败数" />
      </el-table>
    </section>

    <section class="section">
      <div class="toolbar">
        <strong>当前连续失败</strong>
      </div>
      <el-table :data="trends?.current_failures ?? []" stripe>
        <el-table-column prop="check_id" label="检查 ID" width="100" />
        <el-table-column prop="consecutive_failures" label="连续失败" width="120" />
        <el-table-column prop="last_failure_at" label="最近失败" />
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { api, type TrendSummary } from '../api';

const trends = ref<TrendSummary | null>(null);
const buckets = computed(() => Object.values(trends.value?.windows ?? {}));

async function load() {
  trends.value = await api.trends();
}

onMounted(load);
</script>

