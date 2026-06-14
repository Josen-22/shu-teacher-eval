# ClaudeCode Handoff

## 项目结论

- 项目目录已经统一到当前路径：
  - `D:\AppGallery\trae文件\management college\管院教师系统评价`
- 上一级 `management college` 中与本项目重复的副本已清理。
- 当前项目可以本地运行。

## 已验证内容

- `py app.py` 可启动 Flask 服务
- 服务地址为 `http://127.0.0.1:5000`
- `/login` 可正常返回登录页
- `/api/me` 未登录返回 `401`
- 注册后 `/api/me` 返回 `200`
- `/api/teachers` 返回 `200`
- 当前教师数约 `139`

## 关键路径

- 应用入口：`backend/app.py`
- 页面模板：`backend/templates/index.html`
- 登录页：`backend/templates/login.html`
- 数据模型：`backend/models.py`
- 抓取脚本：`backend/scraper.py`
- 教师数据：`backend/teachers.json`
- 数据库：`instance/management_college.db`
- 课程库：`courses_catalog_from_text.json`

## 环境说明

- 当前本机可用 `py`
- 已补充 `requirements.txt`
- 当前代码基于 Flask + SQLite
- 前端主页面是服务端模板 + Vue CDN + Tailwind CDN

## 已知问题

- 启动时有 `RequestsDependencyWarning`，暂不阻塞开发
- 课程数据中存在 OCR 脏数据，例如课程名乱码或识别异常
- 当前是本地开发态，不是正式生产部署方案

## 今晚上线优先级建议

1. 先确认要上线的是“内网演示版”还是“公网正式版”
2. 补一遍 UI 文案和明显乱码数据
3. 手工回归以下流程：
   - 注册
   - 登录
   - 浏览教师列表
   - 查看教师详情
   - 添加课程
   - 提交评价
4. 明确生产配置：
   - `SECRET_KEY`
   - `APP_ENV=production`
   - `COOKIE_SECURE`
   - 反向代理或进程托管方式
5. 若今晚只是先稳定上线，可优先保证主链路和数据展示，不必先做大重构

## 建议 ClaudeCode 第一轮动作

- 检查并补齐部署方案
- 清理首页、教师详情页的可见问题
- 修复明显乱码课程名
- 增加最小化运行文档或启动脚本
- 如果要上线到 Windows 机器，可考虑 `waitress`

## 备注

- 本地运行验证记录在 `debug-teacher-eval-server-check.md`
- 如需重新验证，直接在 `backend/` 下运行：

```powershell
py app.py
```
