<template>
  <div class="files-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>文件浏览</h2>
          <div class="header-actions">
            <el-button type="primary" @click="fetchFiles" size="small" :loading="loading">刷新</el-button>
          </div>
        </div>
      </template>
      
      <div class="path-navigator">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item>
            <a @click="navigateTo('/')">根目录</a>
          </el-breadcrumb-item>
          <template v-for="(part, index) in pathParts" :key="index">
            <el-breadcrumb-item>
              <a @click="navigateTo(getPathUpTo(index))">{{ part }}</a>
            </el-breadcrumb-item>
          </template>
        </el-breadcrumb>
      </div>
      
      <div v-loading="loading">
        <template v-if="currentDirContents.type === 'directory'">
          <el-table :data="currentDirContents.items" style="width: 100%">
            <el-table-column label="名称" min-width="250">
              <template #default="scope">
                <div class="file-item">
                  <el-icon v-if="scope.row.type === 'directory'"><el-icon-folder /></el-icon>
                  <el-icon v-else><el-icon-document /></el-icon>
                  <a @click="handleItemClick(scope.row)" class="file-name">{{ scope.row.name }}</a>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="100">
              <template #default="scope">
                <el-tag size="small" :type="scope.row.type === 'directory' ? 'primary' : 'info'">
                  {{ scope.row.type === 'directory' ? '文件夹' : '文件' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="size" label="大小" width="120">
              <template #default="scope">
                {{ formatFileSize(scope.row.size) }}
              </template>
            </el-table-column>
            <el-table-column prop="modified" label="修改时间" width="180">
              <template #default="scope">
                {{ formatDate(scope.row.modified) }}
              </template>
            </el-table-column>
          </el-table>
        </template>
        
        <template v-else-if="currentDirContents.type === 'file'">
          <div class="file-details">
            <h3>文件详情</h3>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="文件名">{{ currentDirContents.name }}</el-descriptions-item>
              <el-descriptions-item label="大小">{{ formatFileSize(currentDirContents.size) }}</el-descriptions-item>
              <el-descriptions-item label="修改时间">{{ formatDate(currentDirContents.modified) }}</el-descriptions-item>
            </el-descriptions>
            <div class="file-actions">
              <el-button type="primary" @click="navigateBack" size="small">返回上级目录</el-button>
            </div>
          </div>
        </template>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const currentPath = ref('/')
const currentDirContents = ref({ type: 'directory', items: [] })
const loading = ref(false)

// 计算当前路径的各部分
const pathParts = computed(() => {
  return currentPath.value === '/' ? [] : currentPath.value.split('/').filter(Boolean)
})

// 获取到指定索引的路径
const getPathUpTo = (index) => {
  return '/' + pathParts.value.slice(0, index + 1).join('/')
}

// 导航到指定路径
const navigateTo = (path) => {
  currentPath.value = path
  fetchFiles()
}

// 导航回上级目录
const navigateBack = () => {
  if (currentPath.value === '/') return
  
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  currentPath.value = parts.length ? '/' + parts.join('/') : '/'
  fetchFiles()
}

// 处理点击文件或目录
const handleItemClick = (item) => {
  if (item.type === 'directory') {
    navigateTo(`${currentPath.value}${currentPath.value.endsWith('/') ? '' : '/'}${item.name}`)
  } else {
    // 对于文件，展示文件详情
    navigateTo(`${currentPath.value}${currentPath.value.endsWith('/') ? '' : '/'}${item.name}`)
  }
}

// 获取文件和目录列表
const fetchFiles = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/files', {
      params: { path: currentPath.value }
    })
    currentDirContents.value = response.data
  } catch (error) {
    ElMessage.error(`获取文件列表失败: ${error.response?.data?.error || error.message}`)
    // 如果获取失败，尝试返回上一级目录
    if (currentPath.value !== '/') {
      navigateBack()
    }
  } finally {
    loading.value = false
  }
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化日期
const formatDate = (dateString) => {
  const date = new Date(dateString)
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
}

onMounted(() => {
  fetchFiles()
})
</script>

<style scoped>
.files-container {
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

.path-navigator {
  margin-bottom: 20px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  cursor: pointer;
  color: #409eff;
}

.file-name:hover {
  text-decoration: underline;
}

.file-details {
  padding: 20px;
}

.file-actions {
  margin-top: 20px;
}
</style> 