<template>
  <div>
    <section class="section">
      <div class="toolbar">
        <strong>模型性能测试</strong>
        <el-button type="primary" @click="openCreate">新增测试</el-button>
      </div>
      <div class="page-hint">选择测试配置后点击运行，运行监控会显示启动状态、日志、图表和分析结果。</div>
    </section>

    <section class="section">
      <div class="toolbar">
        <strong>性能测试数据集</strong>
        <div class="dataset-actions">
          <el-input v-model="datasetUpload.name" placeholder="数据集名称" style="width: 180px" />
          <el-select v-model="datasetUpload.dataset" style="width: 150px">
            <el-option label="openqa JSONL" value="openqa" />
            <el-option label="line_by_line TXT" value="line_by_line" />
          </el-select>
          <el-input v-model="datasetUpload.description" placeholder="描述" style="width: 220px" />
          <input ref="datasetFileInput" type="file" accept=".jsonl,.txt" @change="onDatasetFileChange" />
          <el-button type="primary" :disabled="!datasetUpload.file || !datasetUpload.name" @click="uploadDataset">
            上传数据集
          </el-button>
        </div>
      </div>
      <el-table :data="datasets" stripe>
        <el-table-column prop="name" label="名称" min-width="170" />
        <el-table-column prop="dataset" label="格式" width="130" />
        <el-table-column label="来源" width="100">
          <template #default="{ row }"><el-tag :type="row.source === 'builtin' ? 'success' : 'info'">{{ row.source === 'builtin' ? '内置' : '上传' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="item_count" label="条数" width="90" />
        <el-table-column prop="description" label="说明" min-width="260" show-overflow-tooltip />
        <el-table-column prop="dataset_path" label="路径" min-width="240" show-overflow-tooltip />
        <el-table-column label="操作" width="100">
          <template #default="{ row }"><el-button size="small" @click="previewDataset(row)">预览</el-button></template>
        </el-table-column>
      </el-table>
    </section>

    <section class="section">
      <div class="toolbar">
        <strong>测试配置</strong>
      </div>
      <div class="filter-bar">
        <el-input v-model="filters.search" clearable placeholder="搜索名称或模型" style="width: 260px" @keyup.enter="loadTests" />
        <el-select v-model="filters.instance_id" clearable placeholder="全部实例" style="width: 180px" @change="loadTests">
          <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-button @click="loadTests">查询</el-button>
      </div>
      <el-table :data="tests" stripe @row-click="selectTest">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="实例" width="140">
          <template #default="{ row }">{{ instanceName(row.new_api_instance_id) }}</template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="170" />
        <el-table-column label="数据集" min-width="160">
          <template #default="{ row }">{{ datasetLabel(row.dataset_config) }}</template>
        </el-table-column>
        <el-table-column label="并发阶梯" width="140">
          <template #default="{ row }">{{ formatList(row.load_config.parallel) }}</template>
        </el-table-column>
        <el-table-column label="请求数" width="100">
          <template #default="{ row }">{{ formatList(row.load_config.number) }}</template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :loading="runningTestId === row.id" @click.stop="runTest(row)">运行</el-button>
            <el-button size="small" @click.stop="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click.stop="removeTest(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, sizes, prev, pager, next"
        :total="pagination.total"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :page-sizes="[20, 50, 100]"
        @current-change="loadTests"
        @size-change="loadTests"
      />
    </section>

    <section class="section run-monitor">
      <div class="toolbar">
        <strong>运行监控</strong>
        <div class="dataset-actions">
          <el-button :disabled="!selected" @click="loadRuns">刷新历史</el-button>
          <el-button :disabled="!activeRun" @click="refreshActiveRun">刷新当前运行</el-button>
          <el-button :disabled="!activeRun" type="primary" plain @click="openLogDialog">查看日志</el-button>
          <el-button :disabled="!activeRun" @click="openDetailDialog">查看明细</el-button>
        </div>
      </div>
      <el-alert
        v-if="!activeRun"
        class="form-help"
        type="info"
        :closable="false"
        show-icon
        title="还没有运行中的任务"
        description="点击测试配置表格里的“运行”后，这里会立即显示 Run ID、启动状态、轮询进度、日志和结果图表。"
      />
      <div v-else>
        <div class="run-status-line">
          <el-tag :type="statusType(activeRun.status)" size="large">{{ activeRun.status }}</el-tag>
          <span>Run ID：#{{ activeRun.id }}</span>
          <span>测试 ID：#{{ activeRun.test_id }}</span>
          <span>耗时：{{ formatDuration(activeRun.duration_ms) }}</span>
          <span v-if="activeRun.started_at">开始：{{ activeRun.started_at }}</span>
        </div>
        <el-alert
          class="form-help"
          :type="['pending', 'running'].includes(activeRun.status) ? 'info' : activeRun.status === 'success' ? 'success' : 'error'"
          :closable="false"
          show-icon
          title="当前启动情况"
          :description="runStatusDescription"
        />
      </div>
    </section>

    <section v-if="selected" class="section">
      <div class="toolbar">
        <strong>运行历史：{{ selected.name }}</strong>
        <el-button @click="loadRuns">刷新</el-button>
      </div>
      <el-table :data="runs" stripe @row-click="selectRun">
        <el-table-column prop="id" label="Run ID" width="90" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="耗时" width="120">
          <template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column label="推荐并发" width="120">
          <template #default="{ row }">{{ valueOf(row.analysis, 'recommended_parallel') }}</template>
        </el-table-column>
        <el-table-column label="最佳吞吐" width="120">
          <template #default="{ row }">{{ valueOf(row.summary, 'best_throughput') }}</template>
        </el-table-column>
        <el-table-column prop="error" label="错误" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="190" />
        <el-table-column label="明细" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click.stop="viewRunDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, sizes, prev, pager, next"
        :total="runPagination.total"
        v-model:current-page="runPagination.page"
        v-model:page-size="runPagination.page_size"
        :page-sizes="[20, 50, 100]"
        @current-change="loadRuns"
        @size-change="loadRuns"
      />
    </section>

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑模型性能测试' : '新增模型性能测试'" width="900px">
      <el-form label-position="top">
        <div class="template-row">
          <span>配置模板</span>
          <el-button size="small" @click="applyTemplate('smoke')">轻量冒烟</el-button>
          <el-button size="small" @click="applyTemplate('normal')">常规压测</el-button>
          <el-button size="small" @click="applyTemplate('capacity')">容量探测</el-button>
        </div>
        <div class="grid-two">
          <el-form-item label="名称"><el-input v-model="form.name" placeholder="如 qwen-chat 常规压测" /></el-form-item>
          <el-form-item label="模型名"><el-input v-model="form.model_name" placeholder="如 qwen-plus" /></el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item label="new-api 实例">
            <el-select v-model="form.new_api_instance_id" clearable placeholder="默认实例" style="width: 100%">
              <el-option v-for="item in instances" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="接口路径">
            <el-input v-model="form.endpoint" />
            <div class="field-tip">OpenAI 兼容 Chat Completions 默认使用 /v1/chat/completions。</div>
          </el-form-item>
        </div>
        <el-form-item label="数据集">
          <template #label>
            <span class="label-with-tip">
              数据集
              <el-tooltip placement="top" content="openqa 使用 JSONL，每行包含 question 字段；line_by_line 使用 TXT，每行一个 prompt。接口冒烟选内置集，业务容量评估上传真实高频问题。">
                <span class="tip-icon">?</span>
              </el-tooltip>
            </span>
          </template>
          <el-select v-model="selectedDatasetName" placeholder="选择压测数据集" style="width: 100%">
            <el-option
              v-for="item in datasets"
              :key="item.name"
              :label="`${item.name} · ${item.dataset} · ${item.item_count} 条 · ${item.source === 'builtin' ? '内置' : '上传'}`"
              :value="item.name"
            />
          </el-select>
          <div class="field-tip">不知道选哪个时使用“内置中文问答轻量集”；要贴近业务容量，请上传真实用户问题。</div>
        </el-form-item>
        <div class="grid-two">
          <el-form-item>
            <template #label>
              <span class="label-with-tip">
                并发阶梯
                <el-tooltip placement="top" content="例如 1,2,4,8 表示按 4 档依次运行。建议从小到大，观察吞吐是否继续上升、P95 是否明显变差。">
                  <span class="tip-icon">?</span>
                </el-tooltip>
              </span>
            </template>
            <el-input v-model="parallelText" placeholder="1,2,4,8" />
            <div class="field-tip">逐档压测，例如 1,2,4,8。不要一开始就填过大的并发。</div>
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="label-with-tip">
                每档请求数
                <el-tooltip placement="top" content="单个数字会用于所有并发档；多个数字会按并发顺序匹配。请求数越大结果越稳定，但运行时间和成本越高。">
                  <span class="tip-icon">?</span>
                </el-tooltip>
              </span>
            </template>
            <el-input v-model="numberText" placeholder="50 或 20,50,100" />
            <div class="field-tip">单个数字会用于所有并发档；多个数字会按并发顺序匹配。</div>
          </el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item label="读取超时秒"><el-input-number v-model="readTimeout" :min="1" style="width: 100%" /></el-form-item>
          <el-form-item label="最大输出 token"><el-input-number v-model="maxTokens" :min="1" style="width: 100%" /></el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item label="日志频率"><el-input-number v-model="logEveryNQuery" :min="1" style="width: 100%" /></el-form-item>
          <el-form-item label="流式请求"><el-switch v-model="streamEnabled" /></el-form-item>
        </div>
        <div class="grid-two">
          <el-form-item>
            <template #label>
              <span class="label-with-tip">
                最大错误率
                <el-tooltip placement="top" content="填写百分比。1 表示最多允许 1% 请求失败；超过阈值的并发点不会被推荐。">
                  <span class="tip-icon">?</span>
                </el-tooltip>
              </span>
            </template>
            <el-input-number v-model="maxErrorRatePercent" :min="0" :max="100" :step="0.1" style="width: 100%" />
            <div class="field-tip">填写百分比。1 表示最多允许 1% 请求失败。</div>
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="label-with-tip">
                P95 延迟阈值 ms
                <el-tooltip placement="top" content="95% 请求耗时低于该值。推荐并发会优先选择低于该阈值的最高并发点。">
                  <span class="tip-icon">?</span>
                </el-tooltip>
              </span>
            </template>
            <el-input-number v-model="maxP95LatencyMs" :min="0" :step="100" style="width: 100%" />
            <div class="field-tip">推荐并发会优先选择低于该 P95 延迟的最高并发。</div>
          </el-form-item>
        </div>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
        <el-collapse>
          <el-collapse-item title="高级 EvalScope 参数 JSON" name="advanced">
            <el-input v-model="extraArgsText" type="textarea" :rows="7" class="json-editor" />
            <div class="field-tip">用于补充 headers、temperature、top_p、query_template 等高级参数；普通测试可以保持空对象。</div>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTest">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewDialog" title="数据集预览" width="720px">
      <div v-if="previewingDataset">
        <div class="preview-meta">
          <el-tag>{{ previewingDataset.dataset }}</el-tag>
          <span>{{ previewingDataset.item_count }} 条</span>
          <span>{{ previewingDataset.dataset_path }}</span>
        </div>
        <ol class="preview-list">
          <li v-for="item in previewingDataset.preview" :key="item">{{ item }}</li>
        </ol>
      </div>
    </el-dialog>

    <el-dialog v-model="detailDialog" :title="activeRun ? `运行明细 #${activeRun.id}` : '运行明细'" width="1080px" @opened="renderCharts">
      <div v-if="activeRun">
        <div class="metrics">
          <div class="metric">
            <div class="metric-label">状态</div>
            <div class="metric-value compact">{{ activeRun.status }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">推荐并发</div>
            <div class="metric-value">{{ valueOf(activeRun.analysis, 'recommended_parallel') }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">最佳 RPS</div>
            <div class="metric-value">{{ numberTextValue(valueOf(activeRun.summary, 'best_throughput')) }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">最大错误率</div>
            <div class="metric-value">{{ percentValue(valueOf(activeRun.summary, 'max_error_rate')) }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">总请求</div>
            <div class="metric-value">{{ valueOf(activeRun.summary, 'total_requests') }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">成功 / 失败</div>
            <div class="metric-value compact">{{ valueOf(activeRun.summary, 'success_requests') }} / {{ valueOf(activeRun.summary, 'failed_requests') }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">最佳 P95 延迟</div>
            <div class="metric-value compact">{{ formatSeconds(valueOf(activeRun.summary, 'best_p95_latency_s')) }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">输出吞吐</div>
            <div class="metric-value compact">{{ numberTextValue(valueOf(activeRun.summary, 'best_output_throughput')) }} tok/s</div>
          </div>
        </div>

        <el-alert
          class="form-help"
          :type="activeRun.analysis?.passed ? 'success' : 'warning'"
          :closable="false"
          show-icon
          title="分析结论"
          :description="String(activeRun.analysis?.recommendation ?? '暂无分析结论，等待 EvalScope 输出完成。')"
        />

        <div class="chart-grid">
          <div ref="throughputChart" class="chart-box"></div>
          <div ref="latencyChart" class="chart-box"></div>
          <div ref="errorChart" class="chart-box"></div>
          <div ref="tokensChart" class="chart-box"></div>
        </div>

        <el-table :data="chartPoints" stripe>
          <el-table-column prop="parallel" label="并发" width="80" />
          <el-table-column label="请求" width="90">
            <template #default="{ row }">{{ row.total_requests ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="成功率" width="100">
            <template #default="{ row }">{{ successRate(row) }}</template>
          </el-table-column>
          <el-table-column label="RPS" width="100">
            <template #default="{ row }">{{ numberTextValue(row.throughput) }}</template>
          </el-table-column>
          <el-table-column label="平均延迟" width="110">
            <template #default="{ row }">{{ formatSeconds(row.avg_latency_s) }}</template>
          </el-table-column>
          <el-table-column label="P95" width="100">
            <template #default="{ row }">{{ formatSeconds(row.p95_latency_s) }}</template>
          </el-table-column>
          <el-table-column label="P99" width="100">
            <template #default="{ row }">{{ formatSeconds(row.p99_latency_s) }}</template>
          </el-table-column>
          <el-table-column label="TTFT" width="110">
            <template #default="{ row }">{{ formatMs(row.ttft_ms) }}</template>
          </el-table-column>
          <el-table-column label="TPOT" width="110">
            <template #default="{ row }">{{ formatMs(row.tpot_ms) }}</template>
          </el-table-column>
          <el-table-column label="输出 tok/s" width="120">
            <template #default="{ row }">{{ numberTextValue(row.tokens_per_second) }}</template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="detailDialog = false">关闭</el-button>
        <el-button type="primary" @click="openLogDialog">查看日志</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logDialog" :title="activeRun ? `执行日志 #${activeRun.id}` : '执行日志'" width="980px" @opened="onLogDialogOpened" @closed="onLogDialogClosed">
      <div class="toolbar compact-toolbar">
        <strong>{{ activeRun?.status ?? '-' }}</strong>
        <el-button size="small" @click="loadLogs(true)">刷新日志</el-button>
      </div>
      <pre ref="logBox" class="run-log dialog-log">{{ logText || '暂无日志' }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import {
  api,
  parseJsonObject,
  statusType,
  type ModelPerformanceDataset,
  type ModelPerformanceRun,
  type ModelPerformanceTest,
  type NewApiInstance
} from '../api';

const tests = ref<ModelPerformanceTest[]>([]);
const instances = ref<NewApiInstance[]>([]);
const datasets = ref<ModelPerformanceDataset[]>([]);
const runs = ref<ModelPerformanceRun[]>([]);
const selected = ref<ModelPerformanceTest | null>(null);
const activeRun = ref<ModelPerformanceRun | null>(null);
const runningTestId = ref<number | null>(null);
const pagination = reactive({ page: 1, page_size: 20, total: 0 });
const runPagination = reactive({ page: 1, page_size: 20, total: 0 });
const filters = reactive<{ search: string; instance_id?: number | null }>({ search: '', instance_id: null });

const datasetUpload = reactive<{ name: string; dataset: 'openqa' | 'line_by_line'; description: string; file: File | null }>({
  name: '',
  dataset: 'openqa',
  description: '',
  file: null
});
const datasetFileInput = ref<HTMLInputElement | null>(null);
const previewDialog = ref(false);
const previewingDataset = ref<ModelPerformanceDataset | null>(null);
const detailDialog = ref(false);
const logDialog = ref(false);
const logBox = ref<HTMLElement | null>(null);

const dialogVisible = ref(false);
const editing = ref<ModelPerformanceTest | null>(null);
const form = reactive<Partial<ModelPerformanceTest>>({});
const selectedDatasetName = ref('');
const parallelText = ref('1,2,4');
const numberText = ref('20');
const readTimeout = ref(120);
const maxTokens = ref(128);
const logEveryNQuery = ref(5);
const streamEnabled = ref(true);
const maxErrorRatePercent = ref(1);
const maxP95LatencyMs = ref(10000);
const extraArgsText = ref('{}');
const logText = ref('');
const logOffset = ref(0);
let pollTimer: number | undefined;
let logTimer: number | undefined;
const SELECTED_TEST_STORAGE_KEY = 'ai-vigil-model-performance-selected-test-id';
const SELECTED_RUN_STORAGE_KEY = 'ai-vigil-model-performance-selected-run-id';

const throughputChart = ref<HTMLElement | null>(null);
const latencyChart = ref<HTMLElement | null>(null);
const errorChart = ref<HTMLElement | null>(null);
const tokensChart = ref<HTMLElement | null>(null);
let charts: echarts.ECharts[] = [];

function defaultForm(): Partial<ModelPerformanceTest> {
  return {
    name: '',
    enabled: true,
    model_name: '',
    endpoint: '/v1/chat/completions',
    new_api_instance_id: null,
    dataset_config: {},
    load_config: {},
    threshold_config: {},
    extra_args: {}
  };
}

async function load() {
  await Promise.all([loadTests(), loadDatasets(), loadInstances()]);
}

async function loadInstances() {
  instances.value = await api.instances();
}

async function loadDatasets() {
  datasets.value = await api.modelPerformanceDatasets();
  if (!selectedDatasetName.value && datasets.value.length > 0) selectedDatasetName.value = datasets.value[0].name;
}

async function loadTests() {
  const page = await api.modelPerformanceTests({ ...filters, page: pagination.page, page_size: pagination.page_size });
  tests.value = page.items;
  pagination.total = page.total;
  await restoreSelectedTest();
}

function onDatasetFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  datasetUpload.file = target.files?.[0] ?? null;
}

async function uploadDataset() {
  if (!datasetUpload.file) return;
  await api.uploadModelPerformanceDataset({
    file: datasetUpload.file,
    name: datasetUpload.name,
    dataset: datasetUpload.dataset,
    description: datasetUpload.description
  });
  ElMessage.success('数据集已上传');
  datasetUpload.file = null;
  datasetUpload.name = '';
  datasetUpload.description = '';
  if (datasetFileInput.value) datasetFileInput.value.value = '';
  await loadDatasets();
}

async function previewDataset(row: ModelPerformanceDataset) {
  previewingDataset.value = await api.modelPerformanceDatasetPreview(row.name);
  previewDialog.value = true;
}

async function selectTest(row: ModelPerformanceTest) {
  selected.value = row;
  localStorage.setItem(SELECTED_TEST_STORAGE_KEY, String(row.id));
  activeRun.value = null;
  runs.value = [];
  runPagination.page = 1;
  await loadRuns();
}

async function restoreSelectedTest() {
  if (selected.value && tests.value.some((item) => item.id === selected.value?.id)) return;
  const storedId = Number(localStorage.getItem(SELECTED_TEST_STORAGE_KEY));
  const restored = tests.value.find((item) => item.id === storedId) ?? tests.value[0];
  if (!restored) return;
  selected.value = restored;
  runs.value = [];
  activeRun.value = null;
  runPagination.page = 1;
  await loadRuns();
}

async function loadRuns() {
  if (!selected.value) return;
  const page = await api.modelPerformanceRuns(selected.value.id, {
    page: runPagination.page,
    page_size: runPagination.page_size
  });
  runs.value = page.items;
  runPagination.total = page.total;
  if (!activeRun.value && runs.value.length > 0) {
    const storedRunId = Number(localStorage.getItem(runStorageKey(selected.value.id)));
    const restoredRun = runs.value.find((item) => item.id === storedRunId) ?? runs.value[0];
    await selectRun(restoredRun);
  }
}

async function selectRun(row: ModelPerformanceRun) {
  activeRun.value = await api.modelPerformanceRun(row.id);
  localStorage.setItem(SELECTED_RUN_STORAGE_KEY, String(row.id));
  if (selected.value) localStorage.setItem(runStorageKey(selected.value.id), String(row.id));
  logText.value = '';
  logOffset.value = 0;
  await nextTick();
  await loadLogs(false);
  restartPolling();
}

async function viewRunDetail(row: ModelPerformanceRun) {
  await selectRun(row);
  await openDetailDialog();
}

function openCreate() {
  editing.value = null;
  Object.assign(form, defaultForm());
  selectedDatasetName.value = datasets.value[0]?.name ?? '';
  applyTemplate('smoke');
  extraArgsText.value = '{}';
  dialogVisible.value = true;
}

function openEdit(row: ModelPerformanceTest) {
  editing.value = row;
  Object.assign(form, JSON.parse(JSON.stringify(row)));
  syncFieldsFromConfig(row);
  dialogVisible.value = true;
}

function syncFieldsFromConfig(row: ModelPerformanceTest) {
  const load = row.load_config ?? {};
  const threshold = row.threshold_config ?? {};
  parallelText.value = formatList(load.parallel ?? [1, 2, 4]);
  numberText.value = formatList(load.number ?? 20);
  readTimeout.value = Number(load.read_timeout ?? 120);
  maxTokens.value = Number(load.max_tokens ?? 128);
  logEveryNQuery.value = Number(load.log_every_n_query ?? 5);
  streamEnabled.value = load.stream !== false;
  maxErrorRatePercent.value = Number(threshold.max_error_rate ?? 0.01) * 100;
  maxP95LatencyMs.value = Number(threshold.max_p95_latency_ms ?? 10000);
  selectedDatasetName.value = String(row.dataset_config?.dataset_name || matchDatasetName(row.dataset_config) || datasets.value[0]?.name || '');
  extraArgsText.value = JSON.stringify(row.extra_args ?? {}, null, 2);
}

function applyTemplate(type: 'smoke' | 'normal' | 'capacity') {
  const templates = {
    smoke: { parallel: '1,2', number: '10', timeout: 60, tokens: 80, p95: 8000 },
    normal: { parallel: '1,2,4,8', number: '50', timeout: 120, tokens: 128, p95: 10000 },
    capacity: { parallel: '1,2,4,8,16,32', number: '100', timeout: 180, tokens: 128, p95: 15000 }
  };
  const item = templates[type];
  parallelText.value = item.parallel;
  numberText.value = item.number;
  readTimeout.value = item.timeout;
  maxTokens.value = item.tokens;
  maxP95LatencyMs.value = item.p95;
  logEveryNQuery.value = 5;
  streamEnabled.value = true;
  maxErrorRatePercent.value = 1;
}

async function saveTest() {
  const dataset = datasets.value.find((item) => item.name === selectedDatasetName.value);
  if (!dataset) {
    ElMessage.error('请选择数据集');
    return;
  }
  const payload = {
    ...form,
    dataset_config: {
      dataset_name: dataset.name,
      dataset: dataset.dataset,
      dataset_path: dataset.dataset_path
    },
    load_config: {
      parallel: parseNumberList(parallelText.value),
      number: numberText.value.includes(',') ? parseNumberList(numberText.value) : Number(numberText.value.trim()),
      read_timeout: readTimeout.value,
      max_tokens: maxTokens.value,
      log_every_n_query: logEveryNQuery.value,
      stream: streamEnabled.value
    },
    threshold_config: {
      max_error_rate: maxErrorRatePercent.value / 100,
      max_p95_latency_ms: maxP95LatencyMs.value
    },
    extra_args: parseJsonObject(extraArgsText.value)
  };
  if (editing.value?.id) {
    await api.updateModelPerformanceTest(editing.value.id, payload);
  } else {
    await api.createModelPerformanceTest(payload);
  }
  dialogVisible.value = false;
  ElMessage.success('已保存');
  await loadTests();
}

async function removeTest(row: ModelPerformanceTest) {
  await ElMessageBox.confirm(`确认删除模型性能测试「${row.name}」？`, '删除确认', { type: 'warning' });
  await api.deleteModelPerformanceTest(row.id);
  if (selected.value?.id === row.id) {
    selected.value = null;
    activeRun.value = null;
    runs.value = [];
    localStorage.removeItem(SELECTED_TEST_STORAGE_KEY);
    localStorage.removeItem(runStorageKey(row.id));
  }
  ElMessage.success('已删除');
  await loadTests();
}

async function runTest(row: ModelPerformanceTest) {
  runningTestId.value = row.id;
  try {
    const run = await api.runModelPerformanceTest(row.id);
    selected.value = row;
    localStorage.setItem(SELECTED_TEST_STORAGE_KEY, String(row.id));
    activeRun.value = run;
    logText.value = '已提交后台任务，正在等待 EvalScope 启动...\n';
    logOffset.value = 0;
    await nextTick();
    restartPolling();
    await loadRuns();
    await selectRun(run);
    ElMessage.success(`已启动后台性能测试，Run ID #${run.id}`);
  } finally {
    runningTestId.value = null;
  }
}

async function refreshActiveRun() {
  if (!activeRun.value) return;
  activeRun.value = await api.modelPerformanceRun(activeRun.value.id);
  if (detailDialog.value) {
    await nextTick();
    renderCharts();
  }
}

async function loadLogs(reset: boolean) {
  if (!activeRun.value) return;
  if (reset) {
    logText.value = '';
    logOffset.value = 0;
  }
  const result = await api.modelPerformanceRunLogs(activeRun.value.id, logOffset.value);
  logText.value += result.content;
  logOffset.value = result.next_offset;
  await nextTick();
  scrollLogToBottom();
}

function restartPolling() {
  clearTimers();
  if (!activeRun.value || !['pending', 'running'].includes(activeRun.value.status)) return;
  pollTimer = window.setInterval(async () => {
    await refreshActiveRun();
    if (activeRun.value && !['pending', 'running'].includes(activeRun.value.status)) {
      clearTimers();
      await loadRuns();
      await loadLogs(false);
    }
  }, 3000);
  if (logDialog.value) {
    logTimer = window.setInterval(() => loadLogs(false), 2000);
  }
}

function clearTimers() {
  if (pollTimer) window.clearInterval(pollTimer);
  if (logTimer) window.clearInterval(logTimer);
  pollTimer = undefined;
  logTimer = undefined;
}

function renderCharts() {
  if (!detailDialog.value) return;
  disposeCharts();
  const points = ((activeRun.value?.chart_data?.points as Array<Record<string, unknown>> | undefined) ?? []);
  const labels = points.map((item) => String(item.parallel ?? '-'));
  charts = [
    buildChart(throughputChart.value, '吞吐量', labels, [{ name: 'QPS', data: points.map((item) => numberValue(item.throughput)) }]),
    buildChart(latencyChart.value, '延迟分位 秒', labels, [
      { name: '平均', data: points.map((item) => numberValue(item.avg_latency_s)) },
      { name: 'P95', data: points.map((item) => numberValue(item.p95_latency_s)) },
      { name: 'P99', data: points.map((item) => numberValue(item.p99_latency_s)) }
    ]),
    buildChart(errorChart.value, '错误率', labels, [{ name: '错误率 %', data: points.map((item) => numberValue(item.error_rate) * 100) }]),
    buildChart(tokensChart.value, 'Token 吞吐', labels, [
      { name: '输出 tok/s', data: points.map((item) => numberValue(item.tokens_per_second)) },
      { name: '总 tok/s', data: points.map((item) => numberValue(item.total_tokens_per_second)) }
    ])
  ].filter(Boolean) as echarts.ECharts[];
}

function buildChart(el: HTMLElement | null, title: string, labels: string[], series: Array<{ name: string; data: number[] }>) {
  if (!el) return null;
  const chart = echarts.init(el);
  chart.setOption({
    title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { top: 34 },
    grid: { left: 48, right: 20, top: 76, bottom: 36 },
    xAxis: { type: 'category', name: '并发', data: labels },
    yAxis: { type: 'value' },
    series: series.map((item) => ({ ...item, type: 'line', smooth: true, symbolSize: 7 }))
  });
  return chart;
}

function disposeCharts() {
  charts.forEach((chart) => chart.dispose());
  charts = [];
}

async function openDetailDialog() {
  if (!activeRun.value) return;
  activeRun.value = await api.modelPerformanceRun(activeRun.value.id);
  detailDialog.value = true;
  await nextTick();
  renderCharts();
}

async function openLogDialog() {
  if (!activeRun.value) return;
  logDialog.value = true;
  await nextTick();
  await loadLogs(logText.value === '');
  startLogPollingIfNeeded();
}

async function onLogDialogOpened() {
  await loadLogs(logText.value === '');
  startLogPollingIfNeeded();
  scrollLogToBottom();
}

function onLogDialogClosed() {
  if (logTimer) window.clearInterval(logTimer);
  logTimer = undefined;
}

function startLogPollingIfNeeded() {
  if (logTimer) window.clearInterval(logTimer);
  if (activeRun.value && ['pending', 'running'].includes(activeRun.value.status)) {
    logTimer = window.setInterval(() => loadLogs(false), 2000);
  }
}

function scrollLogToBottom() {
  if (logBox.value) {
    logBox.value.scrollTop = logBox.value.scrollHeight;
  }
}

function parseNumberList(value: string) {
  return value.split(',').map((item) => Number(item.trim())).filter((item) => Number.isFinite(item) && item > 0);
}

function matchDatasetName(config: Record<string, unknown> | undefined) {
  const path = config?.dataset_path;
  return datasets.value.find((item) => item.dataset_path === path)?.name;
}

function datasetLabel(config: Record<string, unknown> | undefined) {
  return String(config?.dataset_name || matchDatasetName(config) || config?.dataset || '-');
}

function instanceName(id?: number | null) {
  return instances.value.find((item) => item.id === id)?.name ?? '默认实例';
}

function formatList(value: unknown) {
  return Array.isArray(value) ? value.join(', ') : String(value ?? '-');
}

function valueOf(obj: Record<string, unknown> | undefined, key: string) {
  const value = obj?.[key];
  return value === undefined || value === null || value === '' ? '-' : value;
}

function numberValue(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function percentValue(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : '-';
}

function runStorageKey(testId: number) {
  return `${SELECTED_RUN_STORAGE_KEY}:${testId}`;
}

const runStatusDescription = computed(() => {
  if (!activeRun.value) return '';
  if (activeRun.value.status === 'pending') return '任务已创建，正在等待后端调度启动 EvalScope。';
  if (activeRun.value.status === 'running') return 'EvalScope 已启动，系统正在自动轮询状态和增量日志。';
  if (activeRun.value.status === 'success') return '运行已完成，下面可以查看图表、分析结论和完整日志。';
  return activeRun.value.error ? `运行失败：${activeRun.value.error}` : '运行失败，请查看执行日志。';
});

const chartPoints = computed(() => ((activeRun.value?.chart_data?.points as Array<Record<string, unknown>> | undefined) ?? []));

function formatDuration(ms: unknown) {
  const value = Number(ms);
  if (!Number.isFinite(value)) return '-';
  const seconds = value / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} 秒`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes} 分 ${rest} 秒`;
}

function formatSeconds(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '-';
  if (number < 60) return `${number.toFixed(2)} 秒`;
  const minutes = Math.floor(number / 60);
  const rest = Math.round(number % 60);
  return `${minutes} 分 ${rest} 秒`;
}

function formatMs(value: unknown) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '-';
  if (number >= 1000) return `${(number / 1000).toFixed(2)} 秒`;
  return `${number.toFixed(0)} ms`;
}

function numberTextValue(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : '-';
}

function successRate(row: Record<string, unknown>) {
  const total = Number(row.total_requests);
  const success = Number(row.success_requests);
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(success)) return '-';
  return `${((success / total) * 100).toFixed(1)}%`;
}

onMounted(load);
onBeforeUnmount(() => {
  clearTimers();
  disposeCharts();
});
</script>

<style scoped>
.dataset-actions,
.template-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.template-row {
  margin-bottom: 16px;
}

.page-hint {
  color: #64748b;
  line-height: 1.5;
}

.label-with-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tip-icon {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  border: 1px solid #94a3b8;
  color: #64748b;
  font-size: 11px;
  line-height: 1;
  cursor: help;
}

.run-monitor {
  border-color: #9cc9ff;
}

.run-status-line {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  color: #475569;
}

.metric-value.compact {
  font-size: 22px;
  line-height: 1.3;
  word-break: break-word;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin: 18px 0;
}

.chart-box {
  min-height: 300px;
  border: 1px solid #d9e4ef;
  border-radius: 8px;
  background: #ffffff;
}

.run-log {
  min-height: 220px;
  max-height: 460px;
  overflow: auto;
  background: #0f172a;
  color: #dbeafe;
  border-radius: 8px;
  padding: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
}

.dialog-log {
  min-height: 420px;
  max-height: 68vh;
}

.preview-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  color: #64748b;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.preview-list {
  line-height: 1.7;
  padding-left: 22px;
}

@media (max-width: 900px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
