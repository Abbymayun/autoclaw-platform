# ⚡ AutoClaw Platform

对标 AutoClaw 的网页版 AI 助手平台。

## 功能模块

| 模块 | 功能 |
|------|------|
| 💬 对话 | 多轮AI对话，WebSocket流式输出，上下文记忆 |
| 🌐 浏览器 | 打开网页、截图、搜索 |
| 📁 文件 | 上传/管理文件 |
| ⏰ 定时任务 | Cron定时触发 |
| 🚀 部署 | GitHub推送 + 一键部署到云服务器 |
| ⚙️ 设置 | API配置管理 |

## 技术栈

- **后端**: Python FastAPI + WebSocket + APScheduler + Playwright
- **前端**: 原生 HTML/CSS/JS（零依赖，单文件）

## 本地运行

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
python main.py
# 打开 http://localhost:8000
```

## Docker 运行

```bash
docker-compose up -d
```

---

## ☁️ 阿里云服务器部署指南

### 1. 购买服务器

1. 打开 [aliyun.com](https://www.aliyun.com) → 产品 → 云服务器ECS
2. 推荐配置（入门够用）：
   - **实例**: ecs.c7.large（2核4G）或 ecs.t6-c1m2.large
   - **系统**: Ubuntu 22.04 / CentOS 7.9
   - **硬盘**: 40GB 系统盘
   - **带宽**: 按量 5Mbps（用多少算多少）
   - **价格**: 约 ¥100-200/月（首次购买有折扣）
3. 地域选离你近的（华东/杭州）
4. 安全组：开放 **8000** 端口 + **22** (SSH)

### 2. 连接服务器

```bash
# 下载阿里云给的 .pem 密钥或设置密码后：
ssh root@你的公网IP
```

### 3. 服务器环境

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | bash
# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 4. 部署项目

```bash
# 在服务器上：
git clone https://github.com/你的用户名/autoclaw-platform.git
cd autoclaw-platform
docker-compose up -d
# 访问 http://你的公网IP:8000
```

### 5. 配置 HTTPS（可选）

```bash
# 安装 Nginx + Certbot
apt install nginx certbot python3-certbot-nginx -y
# 配置反向代理到 8000 端口
# 申请免费 SSL 证书
certbot --nginx -d 你的域名
```

---

## GitHub Secrets 配置（自动部署用）

在 GitHub 仓库 → Settings → Secrets → Actions 添加：

- `ALIYUN_USERNAME` - 阿里云容器镜像用户名
- `ALIYUN_PASSWORD` - 阿里云容器镜像密码
- `SSH_HOST` - 服务器公网IP
- `SSH_KEY` - 服务器SSH私钥内容

配置后，每次 `git push` 自动构建+部署。

---

## 配置说明

首次使用在网页设置页填写：
- **API地址**: 你的LLM API地址
- **API Key**: API密钥
- **模型**: 默认模型名称
