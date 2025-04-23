<template>
  <div class="dashboard-container">
    <el-card class="dashboard-card">
      <template #header>
        <div class="card-header">
          <h2>同步状态</h2>
        </div>
      </template>
      <div class="status-container">
        <el-tag :type="syncStatus === 'running' ? 'success' : 'info'" size="large">
          {{ syncStatus === 'running' ? '正在同步' : '已停止' }}
        </el-tag>
        <div class="action-buttons">
          <el-button type="primary" :disabled="syncStatus === 'running'" @click="startSync">开始同步</el-button>
          <el-button type="danger" :disabled="syncStatus !== 'running'" @click="stopSync">停止同步</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="dashboard-card">
      <template #header>
        <div class="card-header">
          <h2>连接测试</h2>
        </div>
      </template>
      <div class="connection-test">
        <el-button type="primary" @click="testConnection" :loading="testing">测试 OSS 连接</el-button>
        <span v-if="connectionStatus" class="connection-status" :class="{ 'success': connectionOk, 'error': !connectionOk }">
          {{ connectionStatus }}
        </span>
      </div>
    </el-card>

    <el-card class="dashboard-card">
      <template #header>
        <div class="card-header">
          <h2>最近日志</h2>
          <el-button type="text" @click="$router.push('/logs')">查看全部</el-button>
        </div>
      </template>
      <el-table :data="recentLogs" style="width: 100%">
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
import { ElMessage } from 'element-plus'

const syncStatus = ref('stopped')
const connectionStatus = ref('')
const connectionOk = ref(false)
const testing = ref(false)
const recentLogs = ref([])
let logsTimer = null

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

// 获取同步状态
const getStatus = async () => {
  try {
    const response = await axios.get('/api/config')
    syncStatus.value = response.data.sync_status || 'stopped'
  } catch (error) {
    console.error('获取状态失败', error)
  }
}

// 开始同步
const startSync = async () => {
  try {
    await axios.post('/api/sync/start')
    ElMessage.success('同步任务已开始')
    syncStatus.value = 'running'
  } catch (error) {
    console.error('开始同步失败', error)
  }
}

// 停止同步
const stopSync = async () => {
  try {
    await axios.post('/api/sync/stop')
    ElMessage.success('同步任务已停止')
    syncStatus.value = 'stopped'
  } catch (error) {
    console.error('停止同步失败', error)
  }
}

// 测试连接
const testConnection = async () => {
  testing.value = true
  connectionStatus.value = '正在测试连接...'
  try {
    await axios.get('/api/test-connection')
    connectionStatus.value = '连接成功'
    connectionOk.value = true
  } catch (error) {
    connectionStatus.value = `连接失败: ${error.response?.data?.message || error.message}`
    connectionOk.value = false
  } finally {
    testing.value = false
  }
}

// 获取最近日志
const getRecentLogs = async () => {
  try {
    const response = await axios.get('/api/logs')
    recentLogs.value = response.data.slice(0, 5)
  } catch (error) {
    console.error('获取日志失败', error)
  }
}

// 定时更新日志和状态
const setupTimers = () => {
  logsTimer = setInterval(() => {
    getRecentLogs()
    getStatus()
  }, 5000)
}

onMounted(() => {
  getStatus()
  getRecentLogs()
  setupTimers()
})

onUnmounted(() => {
  if (logsTimer) clearInterval(logsTimer)
})
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dashboard-card {
  margin-bottom: 20px;
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

.status-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.connection-test {
  display: flex;
  align-items: center;
  gap: 20px;
}

.connection-status {
  font-weight: bold;
}

.connection-status.success {
  color: #67c23a;
}

.connection-status.error {
  color: #f56c6c;
}
</style> 