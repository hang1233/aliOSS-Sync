<template>
  <div class="app-container">
    <el-config-provider>
      <el-container>
        <el-header>
          <div class="header-container">
            <h1>OSS同步工具</h1>
          </div>
        </el-header>
        <el-container>
          <el-aside width="200px">
            <el-menu :router="true" class="el-menu-vertical">
              <el-menu-item index="/">
                <el-icon><el-icon-monitor /></el-icon>
                <span>控制面板</span>
              </el-menu-item>
              <el-menu-item index="/files">
                <el-icon><el-icon-folder /></el-icon>
                <span>文件浏览</span>
              </el-menu-item>
              <el-menu-item index="/logs">
                <el-icon><el-icon-document /></el-icon>
                <span>日志记录</span>
              </el-menu-item>
              <el-menu-item index="/settings">
                <el-icon><el-icon-setting /></el-icon>
                <span>配置设置</span>
              </el-menu-item>
            </el-menu>
          </el-aside>
          <el-main>
            <router-view />
          </el-main>
        </el-container>
      </el-container>
    </el-config-provider>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { onMounted } from 'vue'
import axios from 'axios'

// 全局捕获 API 错误
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      ElMessage.error(`请求错误: ${error.response.data.message || error.message}`)
    } else {
      ElMessage.error(`网络错误: ${error.message}`)
    }
    return Promise.reject(error)
  }
)
</script>

<style>
.app-container {
  height: 100vh;
  width: 100%;
}

.el-header {
  background-color: #409eff;
  color: white;
  padding: 0 20px;
}

.header-container {
  display: flex;
  align-items: center;
  height: 100%;
}

.el-aside {
  background-color: #f2f2f2;
}

.el-menu-vertical {
  height: calc(100vh - 60px);
}

.el-main {
  padding: 20px;
}

/* 全局样式 */
body {
  margin: 0;
  padding: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
}
</style> 