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
          <el-button type="primary" :disabled="syncStatus === 'running' || isSyncing" @click="startSync">开始同步</el-button>
          <el-button type="danger" :disabled="syncStatus !== 'running'" @click="stopSync">停止同步</el-button>
          <el-tooltip content="如果状态显示错误，请点击重置" placement="top">
            <el-button type="warning" @click="resetSyncStatus">重置状态</el-button>
          </el-tooltip>
        </div>
      </div>
      
      <div v-if="isSyncing" class="sync-progress-container">
        <h3>同步进度</h3>
        <div class="current-file" v-if="syncProgress.current_file">
          正在同步: {{ syncProgress.current_file }}
        </div>
        <el-progress 
          :percentage="progressPercentage" 
          :format="progressFormat"
          :status="progressStatus">
        </el-progress>
        <div class="progress-details">
          <span>已处理: {{ syncProgress.processed_files || 0 }} / {{ syncProgress.total_files || 0 }} 文件</span>
          <span v-if="syncProgress.start_time">开始时间: {{ formatDate(syncProgress.start_time) }}</span>
          <span v-if="elapsedTime">已用时间: {{ elapsedTime }}</span>
        </div>
        
        <div class="network-stats">
          <h4>网络传输</h4>
          <div class="network-stats-grid">
            <div class="network-stat-item">
              <div class="stat-label">当前速度:</div>
              <div class="stat-value">{{ formatNetworkSpeed(networkStats.speed) }}</div>
            </div>
            <div class="network-stat-item">
              <div class="stat-label">平均速度:</div>
              <div class="stat-value">{{ formatNetworkSpeed(networkStats.avg_speed) }}</div>
            </div>
            <div class="network-stat-item">
              <div class="stat-label">传输总量:</div>
              <div class="stat-value">{{ formatDataSize(networkStats.total_bytes) }}</div>
            </div>
            <div class="network-stat-item">
              <div class="stat-label">预计剩余时间:</div>
              <div class="stat-value">{{ estimatedTimeRemaining }}</div>
            </div>
          </div>
          
          <div class="speed-chart">
            <div class="speed-indicator" :style="{ width: getSpeedBarWidth() + '%' }">
              <span class="speed-text">{{ formatNetworkSpeed(networkStats.speed) }}</span>
            </div>
          </div>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const syncStatus = ref('stopped')
const connectionStatus = ref('')
const connectionOk = ref(false)
const testing = ref(false)
const recentLogs = ref([])
const isSyncing = ref(false)
const syncProgress = ref({
  total_files: 0,
  processed_files: 0,
  current_file: '',
  start_time: null,
  end_time: null
})
const networkStats = ref({
  speed: 0,
  avg_speed: 0,
  total_bytes: 0,
  last_update: null
})
const elapsedTime = ref('')
const estimatedTimeRemaining = ref('')

// 存储网速历史数据用于图表
const speedHistory = ref([])
const MAX_HISTORY_POINTS = 20

let logsTimer = null
let progressTimer = null

// 计算进度百分比
const progressPercentage = computed(() => {
  if (!syncProgress.value.total_files || syncProgress.value.total_files === 0) return 0
  return Math.min(Math.round((syncProgress.value.processed_files / syncProgress.value.total_files) * 100), 100)
})

// 进度格式化
const progressFormat = () => {
  return `${progressPercentage.value}%`
}

// 进度状态
const progressStatus = computed(() => {
  if (progressPercentage.value === 100) return 'success'
  return ''
})

// 格式化网速
const formatNetworkSpeed = (bytesPerSecond) => {
  if (!bytesPerSecond || bytesPerSecond === 0) return '0 B/s'
  
  const units = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s']
  let value = bytesPerSecond
  let unitIndex = 0
  
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex++
  }
  
  return `${value.toFixed(2)} ${units[unitIndex]}`
}

// 格式化数据大小
const formatDataSize = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unitIndex = 0
  
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex++
  }
  
  return `${value.toFixed(2)} ${units[unitIndex]}`
}

// 计算网速bar宽度，最大10MB/s对应100%
const getSpeedBarWidth = () => {
  const maxSpeed = 10 * 1024 * 1024 // 10MB/s
  const percentage = (networkStats.value.speed / maxSpeed) * 100
  return Math.min(percentage, 100)
}

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
}

// 计算已用时间
const calculateElapsedTime = () => {
  if (!syncProgress.value.start_time) {
    elapsedTime.value = ''
    return
  }

  const startTime = new Date(syncProgress.value.start_time)
  const now = new Date()
  const elapsedMs = now - startTime

  // 转换为人类可读的时间格式
  const seconds = Math.floor(elapsedMs / 1000) % 60
  const minutes = Math.floor(elapsedMs / (1000 * 60)) % 60
  const hours = Math.floor(elapsedMs / (1000 * 60 * 60))

  if (hours > 0) {
    elapsedTime.value = `${hours}小时 ${minutes}分钟 ${seconds}秒`
  } else if (minutes > 0) {
    elapsedTime.value = `${minutes}分钟 ${seconds}秒`
  } else {
    elapsedTime.value = `${seconds}秒`
  }
}

// 计算预计剩余时间
const calculateEstimatedTimeRemaining = () => {
  if (!syncProgress.value.total_files || 
      syncProgress.value.total_files <= 0 || 
      !networkStats.value.avg_speed || 
      networkStats.value.avg_speed <= 0) {
    estimatedTimeRemaining.value = '计算中...'
    return
  }
  
  // 计算剩余的文件数
  const remainingFiles = syncProgress.value.total_files - syncProgress.value.processed_files
  if (remainingFiles <= 0) {
    estimatedTimeRemaining.value = '即将完成'
    return
  }
  
  // 估算剩余数据量(假设每个文件平均大小相同)
  const avgFileSize = networkStats.value.total_bytes / syncProgress.value.processed_files
  const remainingBytes = remainingFiles * avgFileSize
  
  // 计算预计时间
  const remainingSeconds = remainingBytes / networkStats.value.avg_speed
  
  // 转换为人类可读的时间格式
  if (!isFinite(remainingSeconds) || remainingSeconds <= 0) {
    estimatedTimeRemaining.value = '即将完成'
    return
  }
  
  const seconds = Math.floor(remainingSeconds % 60)
  const minutes = Math.floor(remainingSeconds / 60) % 60
  const hours = Math.floor(remainingSeconds / 3600)
  
  if (hours > 0) {
    estimatedTimeRemaining.value = `约 ${hours}小时 ${minutes}分钟`
  } else if (minutes > 0) {
    estimatedTimeRemaining.value = `约 ${minutes}分钟 ${seconds}秒`
  } else {
    estimatedTimeRemaining.value = `约 ${seconds}秒`
  }
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

// 获取同步进度
const getSyncProgress = async () => {
  try {
    const response = await axios.get('/api/sync/status')
    isSyncing.value = response.data.is_syncing
    
    if (response.data.progress) {
      syncProgress.value = response.data.progress
    }
    
    if (response.data.network) {
      networkStats.value = response.data.network
      
      // 更新网速历史
      if (networkStats.value.speed > 0) {
        speedHistory.value.push(networkStats.value.speed)
        if (speedHistory.value.length > MAX_HISTORY_POINTS) {
          speedHistory.value.shift()
        }
      }
    }
    
    calculateElapsedTime()
    calculateEstimatedTimeRemaining()
  } catch (error) {
    console.error('获取同步进度失败', error)
  }
}

// 开始同步
const startSync = async () => {
  try {
    await axios.post('/api/sync/start')
    ElMessage.success('同步任务已开始')
    syncStatus.value = 'running'
    await getSyncProgress()
  } catch (error) {
    if (error.response && error.response.data && error.response.data.message) {
      ElMessage.error(error.response.data.message)
    } else {
      ElMessage.error('开始同步失败')
      console.error('开始同步失败', error)
    }
  }
}

// 停止同步
const stopSync = async () => {
  try {
    await axios.post('/api/sync/stop')
    ElMessage.success('同步任务已停止')
    syncStatus.value = 'stopped'
  } catch (error) {
    ElMessage.error('停止同步失败')
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
  
  progressTimer = setInterval(() => {
    getSyncProgress()
  }, 1000) // 更频繁地更新进度和网速
}

// 重置同步状态
const resetSyncStatus = async () => {
  try {
    await axios.post('/api/sync/reset')
    ElMessage.success('同步状态已重置')
    syncStatus.value = 'stopped'
    isSyncing.value = false
    // 立即更新状态
    await getSyncProgress()
    await getStatus()
  } catch (error) {
    ElMessage.error('重置状态失败')
    console.error('重置状态失败', error)
  }
}

onMounted(() => {
  getStatus()
  getRecentLogs()
  getSyncProgress()
  setupTimers()
})

onUnmounted(() => {
  if (logsTimer) clearInterval(logsTimer)
  if (progressTimer) clearInterval(progressTimer)
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
  margin-bottom: 20px;
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

.sync-progress-container {
  margin-top: 20px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.sync-progress-container h3 {
  margin-top: 0;
  margin-bottom: 10px;
  font-size: 16px;
}

.current-file {
  margin-bottom: 10px;
  font-size: 14px;
  color: #606266;
  word-break: break-all;
}

.progress-details {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  font-size: 14px;
  color: #606266;
}

.network-stats {
  margin-top: 20px;
  border-top: 1px solid #ebeef5;
  padding-top: 15px;
}

.network-stats h4 {
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.network-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
  margin-bottom: 15px;
}

.network-stat-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.stat-label {
  font-size: 13px;
  color: #909399;
}

.stat-value {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.speed-chart {
  height: 24px;
  background-color: #ecf5ff;
  border-radius: 12px;
  margin-top: 15px;
  overflow: hidden;
}

.speed-indicator {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  border-radius: 12px;
  transition: width 0.5s ease;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.speed-text {
  padding: 0 10px;
  color: white;
  font-size: 12px;
  font-weight: bold;
  text-shadow: 0 0 2px rgba(0, 0, 0, 0.5);
}
</style> 