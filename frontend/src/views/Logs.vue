<template>
  <div class="logs-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>同步日志</h2>
          <el-button type="primary" @click="fetchLogs" size="small" :loading="loading">刷新</el-button>
        </div>
      </template>
      
      <el-table :data="logs" style="width: 100%" v-loading="loading">
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="level" label="级别" width="100">
          <template #default="scope">
            <el-tag :type="getLogLevelType(scope.row.level)" size="small">
              {{ scope.row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const logs = ref([])
const loading = ref(false)
let refreshTimer = null

// 格式化日期
const formatDate = (dateString) => {
  const date = new Date(dateString)
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
}

// 获取日志级别对应的类型
const getLogLevelType = (level) => {
  const types = {
    'info': 'info',
    'error': 'danger',
    'warning': 'warning'
  }
  return types[level] || 'info'
}

// 获取日志
const fetchLogs = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/logs')
    logs.value = response.data
  } catch (error) {
    console.error('获取日志失败', error)
  } finally {
    loading.value = false
  }
}

// 设置定时刷新
const setupRefreshTimer = () => {
  refreshTimer = setInterval(() => {
    fetchLogs()
  }, 10000) // 每10秒刷新一次
}

onMounted(() => {
  fetchLogs()
  setupRefreshTimer()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.logs-container {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
}
</style> 