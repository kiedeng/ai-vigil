<template>
  <div class="login-page">
    <section class="login-panel">
      <div class="brand" style="color: #1f2937; margin-bottom: 22px">
        <div class="brand-mark">AI</div>
        <div>
          <div class="brand-title">AI Eye Monitor</div>
          <div class="brand-subtitle" style="color: #64748b">登录控制台</div>
        </div>
      </div>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" autocomplete="current-password" show-password />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" style="margin-bottom: 14px" />
        <el-button type="primary" :loading="loading" style="width: 100%" @click="submit">登录</el-button>
      </el-form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../api';

const router = useRouter();
const username = ref('admin');
const password = ref('');
const error = ref('');
const loading = ref(false);

async function submit() {
  error.value = '';
  loading.value = true;
  try {
    const result = await api.login(username.value, password.value);
    localStorage.setItem('ai-eye-token', result.access_token);
    router.push('/');
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败';
  } finally {
    loading.value = false;
  }
}
</script>

