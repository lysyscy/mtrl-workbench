# 材料报表自动化工作台

> 河南省安装集团第四工程公司机关材料科 · **2 人科室内部工具**。
> 口径与契约**不在本文件复述** —— 业务口径 → 《材料科业务全流程说明书》；交付契约 → `PRD/`；技术口径 → 《技术栈选型分析》。
> ⚠️ 本文件**不写进度**（会静默过期）。完成度一律以「哪条 `ACC-*` 判据点转绿」表达。

---

## 目录

```
backend/     FastAPI 后端（按 MOD-* 垂直切包）
frontend/    Vue3 + Vite + Element Plus 前端
tools/       验收报表（四态）
ops/         工程侧实测底账（i8 契约 / 渲染 / 合计行）＋ 运维件（init_db.sql）
artifacts/   产物体（PDF / 临时 HTML / 导出件，可再生成，不进版本控制）
logs/        运行日志（UTF-8）
.workbuddy/  工作区治理（**计划 ＋ 执行情况**两份活文档 / memory / 其余一律 归档-*）
```

## 环境准备（一次性）

```bash
# 1) 建 venv（Python 3.13）
cd backend
"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" -m venv .venv

# 2) venv 级 pip 配置（国内镜像 · 纯 ASCII · 见 .venv\pip.ini）

# 3) 装依赖
.venv\Scripts\python.exe -m pip install -r requirements.in

# 4) 冻结精确版本（全 == 锁）
.venv\Scripts\python.exe -m pip freeze > requirements.txt

# 5) 依赖审计（新增依赖前必跑）
.venv\Scripts\python.exe -m pip_audit
```

## 跑起来（开发）

```bash
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 数据库迁移

```bash
cd backend
.venv\Scripts\alembic.exe revision --autogenerate -m "说明"
.venv\Scripts\alembic.exe upgrade head
```

## 测试与验收

```bash
cd backend
.venv\Scripts\python.exe -m pytest                 # 单元 / 契约测试

cd ..
backend\.venv\Scripts\python.exe tools\acc_report.py   # 四态验收报表（绿/红/待建/未绑定）
```

⚠️ 两条硬约定：**未绑定 ≠ 通过**；**有红即非零退出**。
⚠️ **顺序**：`acc_report.py` **必须在跑完全套 `pytest` 之后**再跑 —— 单文件 / `--collect-only` 会把绑定清单
   覆盖成「未执行」，整片判据点会**假红**（真绿被压成红，反过来不成立）。
⚠️ `demo/_smoke.js` 是**原型层**自检（文档工作区），**不是**本工程的验收套件。

## 文档漂移自检（改完任何文档就跑一次）

```bash
backend\.venv\Scripts\python.exe tools\doc_audit.py           # 术语 / 用例号 / 路径 / 状态数字
backend\.venv\Scripts\python.exe tools\doc_audit.py --ui      # 顺带跑交付面四检
backend\.venv\Scripts\python.exe tools\doc_audit.py --block   # 打印可粘贴的「当前状态」块
```

⚠️ **文档不会报错，只会静默过期**（本项目最贵的一类事故：`sumrow` 变量未定义静默失效 ·
签名漏认静默漏印）。**有漂移即非零退出**。
⚠️ **留痕不算漂移** —— 日志 / 历史计划 / 已执行的方案 / 交接归档见 `LENIENT_GLOBS`（只报「疑似」）；
若某文件内混有留痕段，用 `<!-- doc_audit:history -->` / `current` 包住。
⚠️ 改了**字段名 / 模块名**时，把旧名加进 `tools/doc_audit.py` 的 `RETIRED_TERMS`，否则以后查不出来。

## 本机环境注意

- 给 Windows 程序（`python.exe` / `node.exe`）传路径**必须用反斜杠**：`D:\工作\...`，不要用 `/d/工作/...`。
- Bash 工具若报 `command not found`，前置：`export PATH="/usr/bin:/bin:/c/Windows/System32:/c/Program Files/nodejs:$PATH"`
- ⚠️ **空输出 ≠ 绿灯**：外部命令该有输出却空白时，先看输出文件里是否报错。
- `pip.ini` / `alembic.ini` **须保持纯 ASCII**（中文注释会导致整份配置失效）。
