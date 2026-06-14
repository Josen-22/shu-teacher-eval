# 管院教师系统评价

上海大学管理学院教师评价系统，本地可运行，当前已验证核心链路可用。

## 当前状态

- 目录已从 `management college` 上一级收拢到当前文件夹。
- 本地启动验证已通过。
- 核心链路已验证：
  - 打开登录页
  - 注册/登录
  - 拉取教师列表

详细验证记录见 `debug-teacher-eval-server-check.md`。

## 目录说明

- `backend/`
  - Flask 后端
  - 模板文件在 `backend/templates/`
  - 数据抓取脚本在 `backend/scraper.py`
- `instance/`
  - SQLite 数据库 `management_college.db`
- `courses_catalog_from_text.json`
  - 课程库数据
- `evaluations_sample.json`
  - 评价导入样例
- 其余 `catalog*`、`chunk*`、`*_raw_ocr.txt`
  - 课程目录提取和 OCR 中间产物，暂时保留，方便后续继续清洗数据

## 本地启动

推荐在项目根目录执行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd backend
py app.py
```

启动后访问：

```text
http://127.0.0.1:5000
```

## 关键文件

- 后端入口：`backend/app.py`
- 数据模型：`backend/models.py`
- 教师主页模板：`backend/templates/index.html`
- 登录页模板：`backend/templates/login.html`
- 教师数据：`backend/teachers.json`
- 数据库：`instance/management_college.db`

## 已知情况

- 当前未登录访问首页会跳转到登录页，这是正常行为。
- 启动时可能出现 `RequestsDependencyWarning`，目前不影响运行。
- 当前使用 SQLite，本地开发没问题；若今晚要正式上线，建议先明确部署机器和反向代理方案。

## 交接

ClaudeCode 接手前建议优先阅读：

- `README.md`
- `CLAUDECODE-HANDOFF.md`
- `debug-teacher-eval-server-check.md`
