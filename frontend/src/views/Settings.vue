<template>
  <div class="settings-container">
    <el-card class="settings-card">
      <template #header>
        <div class="card-header">
          <h2>同步设置</h2>
        </div>
      </template>
      
      <div v-loading="loading">
        <el-form :model="config" label-width="120px">
          <el-form-item label="定时同步">
            <el-switch v-model="config.schedule.enabled" />
          </el-form-item>
          
          <el-form-item label="同步间隔" v-if="config.schedule.enabled">
            <el-input-number 
              v-model="config.schedule.interval" 
              :min="60" 
              :step="300"
              :formatter="formatIntervalSeconds"
              :parser="parseIntervalValue"
            />
            <span class="interval-desc">（最小间隔：60秒）</span>
          </el-form-item>
          
          <el-divider />
          
          <el-form-item label="忽略的文件">
            <div class="ignore-patterns">
              <div v-for="(pattern, index) in config.ignore_patterns" :key="index" class="ignore-pattern-item">
                <el-input v-model="config.ignore_patterns[index]" placeholder="输入忽略模式" />
                <el-button type="danger" @click="removeIgnorePattern(index)" :icon="Delete" circle />
              </div>
              <el-button type="primary" @click="addIgnorePattern">添加忽略模式</el-button>
            </div>
          </el-form-item>
          
          <el-divider />
          
          <el-form-item>
            <el-button type="primary" @click="saveConfig" :loading="saving">保存设置</el-button>
            <el-button @click="fetchConfig">重置</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-card>
    
    <el-card class="settings-card">
      <template #header>
        <div class="card-header">
          <h2>OSS 连接信息</h2>
        </div>
      </template>
      
      <el-alert
        type="info"
        show-icon
        :closable="false"
      >
        <p>OSS 连接信息需通过环境变量或 .env 文件配置，无法在界面上修改。</p>
        <p>请参考 docker-compose.yml 和 .env-example 文件进行配置。</p>
      </el-alert>
      
      <div class="connection-info">
        <el-button type="primary" @click="testConnection" :loading="testing">测试 OSS 连接</el-button>
        <span v-if="connectionStatus" class="connection-status" :class="{ 'success': connectionOk, 'error': !connectionOk }">
          {{ connectionStatus }}
        </span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'

const config = ref({
  schedule: {
    enabled: false,
    interval: 3600
  },
  ignore_patterns: ['.git/', '.DS_Store', '*.tmp']
})

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const connectionStatus = ref('')
const connectionOk = ref(false)

// 获取配置
const fetchConfig = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/config')
    config.value = response.data
  } catch (error) {
    ElMessage.error(`获取配置失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

// 保存配置
const saveConfig = async () => {
  saving.value = true
  try {
    await axios.post('/api/config', config.value)
    ElMessage.success('配置已保存')
  } catch (error) {
    ElMessage.error(`保存配置失败: ${error.message}`)
  } finally {
    saving.value = false
  }
}

// 添加忽略模式
const addIgnorePattern = () => {
  config.value.ignore_patterns.push('')
}

// 删除忽略模式
const removeIgnorePattern = (index) => {
  config.value.ignore_patterns.splice(index, 1)
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

// 格式化秒数为友好显示
const formatIntervalSeconds = (value) => {
  if (value < 60) return `${value} 秒`
  if (value < 3600) return `${Math.floor(value / 60)} 分钟`
  if (value < 86400) return `${Math.floor(value / 3600)} 小时 ${Math.floor((value % 3600) / 60)} 分钟`
  return `${Math.floor(value / 86400)} 天 ${Math.floor((value % 86400) / 3600)} 小时`
}

// 解析输入值
const parseIntervalValue = (value) => {
  if (typeof value === 'string') {
    const nums = value.match(/\d+/g)
    if (nums) {
      return parseInt(nums[0] || 60)
    }
  }
  return value
}

onMounted(() => {
  fetchConfig()
})
</script>

<style scoped>
.settings-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-card {
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

.ignore-patterns {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ignore-pattern-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.connection-info {
  margin-top: 20px;
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

.interval-desc {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style> 