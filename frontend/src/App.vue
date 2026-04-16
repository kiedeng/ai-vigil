<template>
  <RouterView v-if="isLoginPage" />
  <div v-else class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">AI</div>
        <div>
          <div class="brand-title">AI Eye Monitor</div>
          <div class="brand-subtitle">服务与模型监控</div>
        </div>
      </div>
      <nav class="nav">
        <RouterLink to="/">总览</RouterLink>
        <RouterLink to="/checks">检查管理</RouterLink>
        <RouterLink to="/runs">运行历史</RouterLink>
        <RouterLink to="/trends">指标趋势</RouterLink>
        <RouterLink to="/quality">质量回归</RouterLink>
        <RouterLink to="/samples">样本管理</RouterLink>
        <RouterLink to="/models">模型中心</RouterLink>
        <RouterLink to="/alerts">告警配置</RouterLink>
        <RouterLink to="/settings">系统设置</RouterLink>
      </nav>
    </aside>
    <main class="main">
      <div class="topbar">
        <div>
          <h1 class="page-title">{{ title }}</h1>
          <p class="page-subtitle">{{ subtitle }}</p>
        </div>
        <el-button @click="logout">退出登录</el-button>
      </div>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const isLoginPage = computed(() => route.path === '/login');
const title = computed(() => {
  const map: Record<string, string> = {
    '/': '监控总览',
    '/checks': '检查管理',
    '/runs': '运行历史',
    '/trends': '指标趋势',
    '/quality': '质量回归',
    '/samples': '样本管理',
    '/models': '模型中心',
    '/alerts': '告警配置',
    '/settings': '系统设置'
  };
  return map[route.path] ?? 'AI Eye Monitor';
});
const subtitle = computed(() => {
  const map: Record<string, string> = {
    '/': '查看整体可用率、最近运行和告警状态',
    '/checks': '维护模型检查、健康检查和接口内容检查',
    '/runs': '按检查项和状态筛选执行记录',
    '/trends': '查看可用率、错误率、延迟分位和质量通过率',
    '/quality': '维护 Golden Set、标准用例和 AI 评估 Prompt',
    '/samples': '上传音频、图片、文档等检查样本并维护版本',
    '/models': '同步 new-api 模型并配置分类规则',
    '/alerts': '维护通用 Webhook 告警通道',
    '/settings': '维护运行参数和 new-api 基础配置'
  };
  return map[route.path] ?? '';
});

function logout() {
  localStorage.removeItem('ai-eye-token');
  router.push('/login');
}
</script>
