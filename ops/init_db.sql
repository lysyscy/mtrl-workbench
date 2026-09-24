-- ============================================================
-- 材料报表自动化工作台 · 数据库初始化（一次性）
-- 依据：《技术栈选型分析》§3.0/§3.1（PostgreSQL 16 同机服务）
--      · 工程底线的「测试库与开发库物理隔离」
--
-- 执行方式（需要 postgres 超级用户）：
--   "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -f "D:\dev\mtrl-workbench\ops\init_db.sql"
--
-- ⚠️ 执行前把 <PASSWORD> 换成你自己定的强口令，并同步写进 .env（不进版本库）。
-- ============================================================

-- 1) 专用账号（仅本机访问；PG 已 listen_addresses='127.0.0.1'）
CREATE ROLE mtrl LOGIN PASSWORD '<PASSWORD>';

-- 2) 开发库
CREATE DATABASE mtrl_workbench
    OWNER mtrl
    ENCODING 'UTF8'
    LC_COLLATE 'C'
    LC_CTYPE 'C'
    TEMPLATE template0;

-- 3) 测试库（与开发库物理隔离 —— 工程底线）
CREATE DATABASE mtrl_workbench_test
    OWNER mtrl
    ENCODING 'UTF8'
    LC_COLLATE 'C'
    LC_CTYPE 'C'
    TEMPLATE template0;

-- 4) 收回 public schema 的公共建表权，只允许 mtrl 使用（PG 15+ 默认已收紧）
\connect mtrl_workbench
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT  ALL ON SCHEMA public TO mtrl;

\connect mtrl_workbench_test
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT  ALL ON SCHEMA public TO mtrl;

-- 5) 确认
\echo '=== 数据库清单 ==='
SELECT datname FROM pg_database WHERE datname LIKE 'mtrl%';
\echo '=== 角色清单 ==='
SELECT rolname FROM pg_roles WHERE rolname = 'mtrl';
