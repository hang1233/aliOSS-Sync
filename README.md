# OSS同步工具

一个用于同步本地文件到阿里云OSS的现代化网页应用。

## 功能特点

- 同步本地文件到阿里云OSS
- 支持增量同步
- 忽略重复文件
- 现代化网页界面
  - 开始/停止同步
  - 显示最近100条日志
  - 设置定时任务
  - 实时测试OSS连接
  - 查看映射宿主机文件路径内容
- 使用Docker容器在Python 3.10环境下运行
- 通过docker-compose配置OSS参数和映射宿主机文件路径

## 技术栈

- 后端：Python 3.10 + Flask
- 前端：Vue.js + Element UI
- 存储：阿里云OSS (使用oss2库)
- 容器化：Docker + docker-compose

## 部署信息

- 对外端口：2003 