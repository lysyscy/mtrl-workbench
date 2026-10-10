# -*- coding: utf-8 -*-
"""
数据库层：schema 定义 / 连接 / 初始化（含默认配置写入）。
Schema 依据《数据库设计草案_v1.md》v1.5，所有确认规则沉淀在 config 表。
"""
import glob
import json
import os
import sqlite3
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
DB_PATH = os.path.join(DATA_DIR, 'workbench.db')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  phid TEXT DEFAULT '',
  is_small TEXT NOT NULL DEFAULT '否',
  status TEXT NOT NULL DEFAULT '在建',
  sort_order INTEGER NOT NULL DEFAULT 0,
  aliases TEXT NOT NULL DEFAULT '',
  full_name TEXT DEFAULT '',
  display_name TEXT DEFAULT '',
  note TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime')),
  updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS stock_monthly (
  id INTEGER PRIMARY KEY,
  month TEXT NOT NULL,
  project_id INTEGER REFERENCES projects(id),
  仓库 TEXT, 资源分类 TEXT, 资源编码 TEXT, 资源名称 TEXT, 规格型号 TEXT,
  计量单位 TEXT, 物料性质 TEXT,
  期初数量 REAL, 期初金额 REAL, 收数量 REAL, 收单价 REAL, 收金额 REAL,
  发数量 REAL, 发单价 REAL, 发金额 REAL, 结存数量 REAL, 结存金额 REAL,
  source TEXT DEFAULT 'auto',
  import_time TEXT DEFAULT (datetime('now','localtime')),
  UNIQUE(month, 仓库, 资源编码)
);

CREATE TABLE IF NOT EXISTS inv_detail (
  id INTEGER PRIMARY KEY,
  month TEXT NOT NULL,
  project_id INTEGER REFERENCES projects(id),
  序号 TEXT, 仓库 TEXT, 出入库方向 TEXT, 物料性质 TEXT, 物料名称 TEXT, 规格型号 TEXT,
  计量单位 TEXT, 业务类型 TEXT, 项目名称 TEXT, 单据编号 TEXT, 供应商 TEXT,
  班组 TEXT, 部门 TEXT, 单据日期 TEXT, 审核日期 TEXT, 是否作废 TEXT,
  cbs名称 TEXT, wbs名称 TEXT,
  数量 REAL, 不含税单价 REAL, 含税单价 REAL, 金额 REAL, 价税合计 REAL,
  raw_json TEXT,
  source TEXT DEFAULT 'auto',
  import_time TEXT DEFAULT (datetime('now','localtime')),
  UNIQUE(month, 单据编号, 序号)
);

CREATE TABLE IF NOT EXISTS pay_notice (
  id INTEGER PRIMARY KEY,
  单据编码 TEXT UNIQUE NOT NULL,
  单据名称 TEXT, 单据日期 TEXT,
  project_id INTEGER REFERENCES projects(id),
  stat_name TEXT,
  small_name TEXT,
  付款项目 TEXT, 申请人 TEXT, 申请部门 TEXT, 录入人 TEXT,
  付款类型 TEXT, 业务类型 TEXT, 付款属性 TEXT, 付款组织 TEXT, 收款单位 TEXT,
  申请金额 REAL, 审批金额 REAL, 累计实付金额 REAL,
  支付状态 TEXT, 冲红状态 TEXT, 审批状态 TEXT, 打印状态 TEXT,
  记账状态 TEXT, 备注 TEXT,
  biz_class TEXT,
  manual INTEGER NOT NULL DEFAULT 0,
  deleted INTEGER NOT NULL DEFAULT 0,
  confirmed INTEGER NOT NULL DEFAULT 0,
  source_month TEXT,
  source TEXT DEFAULT 'auto',
  import_time TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS pay_plan (
  id INTEGER PRIMARY KEY,
  month TEXT NOT NULL,
  project_id INTEGER REFERENCES projects(id),
  单据号 TEXT, 供应商 TEXT, 单据金额 REAL, 预付款金额 REAL,
  状态 TEXT DEFAULT '未付', 备注 TEXT DEFAULT '',
  notice_id INTEGER REFERENCES pay_notice(id),
  match_status TEXT DEFAULT '待核对'
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pay_plan ON pay_plan(month, 单据号, 供应商);

CREATE TABLE IF NOT EXISTS pay_flow (
  id INTEGER PRIMARY KEY,
  notice_id INTEGER REFERENCES pay_notice(id),
  单据编码 TEXT,
  pay_date TEXT, pay_amount REAL,
  way TEXT DEFAULT 'manual',
  note TEXT DEFAULT '',
  create_time TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS jc_contract (
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  序号 TEXT, 合同日期 TEXT, 材料名称 TEXT, 贸易公司 TEXT, 供应商 TEXT,
  供应商合同总价 REAL, 供应商发票金额 REAL,
  贸易公司合同总价 REAL, 贸易公司发票金额 REAL,
  结算金额 REAL, 付款金额 REAL, 欠款 REAL,
  备注 TEXT, 存档状态 TEXT, 存档序号 TEXT, 寄回状态 TEXT,
  source TEXT DEFAULT 'manual',
  import_time TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS jc_invoice (
  id INTEGER PRIMARY KEY,
  contract_id INTEGER REFERENCES jc_contract(id),
  类型 TEXT, 金额 REAL, 日期 TEXT, 备注 TEXT
);

CREATE TABLE IF NOT EXISTS jc_settle (
  id INTEGER PRIMARY KEY,
  contract_id INTEGER REFERENCES jc_contract(id),
  金额 REAL, 日期 TEXT
);

CREATE TABLE IF NOT EXISTS jc_pay (
  id INTEGER PRIMARY KEY,
  contract_id INTEGER REFERENCES jc_contract(id),
  金额 REAL, 日期 TEXT,
  来源 TEXT DEFAULT 'manual', 关联单据号 TEXT
);

CREATE TABLE IF NOT EXISTS debt_other (
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  month TEXT,
  分类 TEXT, 金额 REAL,
  来源 TEXT DEFAULT 'manual', 备注 TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS mtrl_extract (
  month TEXT NOT NULL,     -- '2026-08'
  cat TEXT NOT NULL,       -- '气体' / '焊材'
  wh TEXT NOT NULL,        -- 仓库（项目名）
  amount REAL NOT NULL,
  PRIMARY KEY (month, cat, wh)
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name TEXT DEFAULT '',
  is_active INTEGER NOT NULL DEFAULT 1,
  i8_account TEXT DEFAULT '',
  i8_password TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS mach_settle (
  id INTEGER PRIMARY KEY,
  project TEXT NOT NULL,      -- 项目名（= projects.name，与 v_debt.project 对齐）
  month TEXT NOT NULL,        -- 'YYYY-MM'
  amount REAL NOT NULL,       -- 机械费月结算金额（手动录入，覆盖通知书自动值）
  note TEXT DEFAULT '',
  operator TEXT DEFAULT '',
  updated_at TEXT DEFAULT '',
  UNIQUE(project, month)
);

CREATE TABLE IF NOT EXISTS config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT DEFAULT (datetime('now','localtime')),
  note TEXT DEFAULT ''
);
'''
BACKUP_DIR = os.path.join(DATA_DIR, 'backup')

# 迁移按版本登记（替代散落的 if-ALTER 判断）；新变更在此追加，勿再手写 ALTER
MIGRATIONS = {
    '001_baseline': ('', '基线 schema（CREATE TABLE IF NOT EXISTS 已保证）'),
    '002_pay_notice_lock': (
        "ALTER TABLE pay_notice ADD COLUMN updated_at TEXT DEFAULT '';"
        "ALTER TABLE pay_notice ADD COLUMN updated_by TEXT DEFAULT '';",
        '两人共用：行级乐观锁字段 + 操作留痕（2026-09-08）'),
    '003_add_project_phid_aliases': (
        "ALTER TABLE projects ADD COLUMN phid TEXT DEFAULT '';"
        "ALTER TABLE projects ADD COLUMN aliases TEXT NOT NULL DEFAULT '';",
        'projects 补 phid/aliases 列（旧库迁移，幂等）'),
    '004_project_mgmt': (
        "ALTER TABLE projects ADD COLUMN full_name TEXT DEFAULT '';"
        "ALTER TABLE projects ADD COLUMN display_name TEXT DEFAULT '';"
        "ALTER TABLE projects ADD COLUMN created_at TEXT DEFAULT '';"
        "ALTER TABLE projects ADD COLUMN updated_at TEXT DEFAULT '';"
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_full_name ON projects(full_name) "
        "WHERE full_name != '' AND full_name NOT LIKE '%小微%';",
        '项目管理：projects 补列 + full_name 部分唯一索引（排除含"小微"的壳全名，因小微多仓库共享壳全名一对多）（2026-09-08）'),
    '005_pay_notice_org': (
        "ALTER TABLE pay_notice ADD COLUMN 付款组织 TEXT DEFAULT '';",
        '付款通知书加付款组织列（2026-09-08）'),
    '006_pay_manage': (
        "ALTER TABLE pay_notice ADD COLUMN 计入统计结算 REAL;"
        "ALTER TABLE pay_notice ADD COLUMN 计入统计付款 REAL;"
        "ALTER TABLE pay_flow ADD COLUMN pay_way TEXT DEFAULT '';"
        "ALTER TABLE pay_flow ADD COLUMN pay_way_note TEXT DEFAULT '';"
        "ALTER TABLE pay_flow ADD COLUMN source TEXT DEFAULT 'manual';"
        "ALTER TABLE pay_flow ADD COLUMN voided INTEGER NOT NULL DEFAULT 0;"
        "ALTER TABLE pay_flow ADD COLUMN request_id TEXT DEFAULT '';"
        "ALTER TABLE pay_flow ADD COLUMN initial_id INTEGER;"
        "ALTER TABLE pay_plan ADD COLUMN 流程金额 REAL;"
        "ALTER TABLE pay_plan ADD COLUMN 已付款金额 REAL;"
        "ALTER TABLE pay_plan ADD COLUMN 付款时间 TEXT DEFAULT '';"
        "ALTER TABLE pay_plan ADD COLUMN 付款方式 TEXT DEFAULT '';"
        "ALTER TABLE pay_plan ADD COLUMN 分类 TEXT DEFAULT '';"
        "CREATE TABLE IF NOT EXISTS pay_flow_log (id INTEGER PRIMARY KEY, flow_id INTEGER, action TEXT DEFAULT '', 旧值 TEXT DEFAULT '', 新值 TEXT DEFAULT '', 操作人 TEXT DEFAULT '', 原因 TEXT DEFAULT '', create_time TEXT DEFAULT (datetime('now','localtime'))) ;"
        "CREATE TABLE IF NOT EXISTS debt_initial (id INTEGER PRIMARY KEY, 项目 TEXT NOT NULL DEFAULT '', 期初结算 REAL DEFAULT 0, 期初付款 REAL DEFAULT 0, 备注 TEXT DEFAULT '', create_time TEXT DEFAULT (datetime('now','localtime'))) ;"
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pay_flow_request ON pay_flow(request_id) WHERE request_id != '';",
        '付款管理：pay_notice 加计入统计两列 + pay_flow 改造(付款方式/来源/撤销/防连点) + pay_plan 扩列 + 留痕表 + 期初占位行（2026-09-09）'),
    '007_debt_initial': (
        "ALTER TABLE debt_initial ADD COLUMN operator TEXT DEFAULT '';"
        "ALTER TABLE debt_initial ADD COLUMN updated_at TEXT DEFAULT '';"
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_debt_initial_project ON debt_initial(项目);",
        '期初占位行：补操作留痕列 + 项目唯一索引（全列，支撑录入 upsert ON CONFLICT(项目)；账=期初+25.12起结算-25.12起付款）（2026-09-09）'),
    '008_user_i8_binding': (
        "ALTER TABLE users ADD COLUMN i8_account TEXT DEFAULT '';"
        "ALTER TABLE users ADD COLUMN i8_password TEXT DEFAULT '';",
        '账号绑定（阶段二）：users 加 i8 账号/密码（i8 密码可逆混淆存，非哈希）（2026-09-09）'),
}

# ---- 默认配置（草案 v1.5 已确认规则；首次初始化写入，之后以库内为准） ----
DEFAULT_CONFIG = {
    # 付款项目 → 统计名。**注意：并非完全退役**——project_sync.py 仍用它把信息化完整名桥接到统计名行；
    # 付款解析（importer）已改用 projects.aliases，不再读它
    'project_map': {
        '河南省龙源纸业股份有限公司热电联产升级改造项目建筑工程施工': '周口太康龙源纸业项目',
        '内蒙古宜化化工有限公司新建3#600TPD套筒窑项目机电安装施工': '内蒙宜化项目',
        '新疆慧能横窑安装项目': '新疆慧能项目',
        '晋江市污泥处置中心一期工程核心设备安装工程': '晋江污泥项目',
        '灵宝市新凌铅业公司“退城入园”多金属综合利用提升改造项目氧化锌浸出、净液车间槽罐制作安装': '灵宝新凌项目',
        '邵武天壕金塘工业园区热源建设项目1×130T/H（2#锅炉）锅炉机组安装工程': '福建南平邵武（天壕）项目',
        '百通宏达热力（泗阳）有限公司热电联产项目#4锅炉建筑及安装工程': '泗阳#4项目',
        '江苏新动力（沭阳）热电有限公司热电联产扩建项目#4炉#3机组建筑安装工程': '沭阳项目',
        '安徽国风矿业发展有限公司年产200万吨钙基新材料一体化项目(深加工厂一期工程)加工区EPC工程项目': '安徽国风项目',
        '三峡能源大规模压缩空气储能系统与关键装备研制及应用示范项目安装施工工程': '三峡储能项目',
        '宜昌邦普88、119、120、121车间工艺安装工程': '宜昌项目',
        '新疆普康生物科技有限公司年产500吨克林霉素醇化物项目机电安装工程施工': '新疆普康项目',
        '许昌安彩光伏玻璃材料（焦锑酸钠）项目（一期）设备采购及安装工程': '许昌安彩项目',
        '杭州山亚南方水泥日产5000吨孰料水泥生产线技改工程': '忽略',
        '第四工程公司 2024小微项目': '__small__',
        '第四工程公司2026年小微项目': '__small__',
        '集团公司第四分公司机关工程': '剔除',
    },
    # 小微合并项目 → 具体小微项目 → 单据名称关键词（2.4 节）
    'small_map': {
        '第四工程公司 2024小微项目': {
            '大唐雷州': ['大唐雷州', '大唐项目', '2024小微大唐'],
            '焦作佰利': ['佰利', '焦作佰利', '2024小微佰利'],
        },
        '第四工程公司2026年小微项目': {
            '兰考金不换': ['兰考'],
        },
    },
    # 剔除规则（2.3 节，按顺序执行；配置可改）
    'exclude_rules': {
        '收款单位': ['资产处集中采购'],
        '录入人': ['梁丽佳'],
        '业务类型': ['付劳务公司款', '付分包工程款', '付劳务工工资', '付材料采购款', '付其他款'],
        '单据名称关键字': ['水电', '水费', '电费', '房租'],
    },
    # 分类规则（2.3 节）
    'classify_rules': {
        '机械锁定业务类型': ['付设备租赁款'],
        '付款类型初判': {'其他支出': '辅材', '付款通知书': '机械'},
    },
    # 已忽略项（2026-09-07 确认）
    'ignored': ['四分鸡东净水厂（浙江元通）164817.55元'],
    # 收发结存 焊材/气体 提取（月度经济分析会用）
    # 气体=白名单（| 分隔精确物料名，仅统计名单内；新气体加名单即可，误伤免疫）；焊材=关键词初筛+排除
    'gas_list': '液氩|氩气|二氧化碳|二氧化碳气|液氧|丙烷|氧气',
    'weld_keywords': '焊丝|焊条|焊锡丝',
    'not_weld': '',
    # 欠款/结算口径（2026-09-08 用户拍板，实现必须遵守）
    'debt_rules': {
        '欠款公式': '结算额 - 已付款金额',
        '发票取数优先': '贸易公司 > 供应商',  # 有贸易公司按贸易公司发票金额；无贸易公司按供应商发票金额
        '一合同多项目': False,               # 该场景不存在，无需兼容
        '录入时机': '科长审批结算流程时见票即录，随时发生、不定时（禁止假设批量更新/定时快照）',
        '数据来源': '信息化系统（不建独立录入功能，走导入）',
    },
}


def get_conn():
    """返回连接（调用方负责关闭）。
    两人共用：加 busy_timeout，写锁被占用时**等待**而不是立刻报 database is locked。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=10000')
    return conn


def backup_db(tag='auto'):
    """安全在线备份：用 SQLite backup API（WAL 模式下也一致，不能直接 copy 文件）；保留最近 8 份"""
    if not os.path.exists(DB_PATH):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    fn = os.path.join(BACKUP_DIR, 'workbench_%s_%s.db' % (time.strftime('%Y%m%d_%H%M%S'), tag))
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(fn)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    _prune_backups(keep=8)
    return fn


def _prune_backups(keep=8):
    try:
        fs = sorted(glob.glob(os.path.join(BACKUP_DIR, 'workbench_*.db')), reverse=True)
        for f in fs[keep:]:
            os.remove(f)
    except OSError:
        pass


def backup_if_needed():
    """启动时按需备份：同一天内只备一次（避免频繁重启刷出一堆副本）"""
    today = time.strftime('%Y%m%d')
    try:
        for f in glob.glob(os.path.join(BACKUP_DIR, 'workbench_*.db')):
            if os.path.basename(f).startswith('workbench_' + today):
                return None
    except OSError:
        pass
    return backup_db('startup')


def _apply_migrations(conn):
    """按版本登记执行迁移（已应用的跳过）。
    逐条执行并 try/except OperationalError，保证 ALTER ADD COLUMN 幂等（列已存在时不报错、可安全重跑）。"""
    for ver, (sql, note) in MIGRATIONS.items():
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version=?', (ver,)).fetchone():
            continue
        if sql:
            for stmt in sql.split(';'):
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    # 幂等：列已存在等场景直接跳过
                    pass
        conn.execute('INSERT INTO schema_migrations(version, note) VALUES(?,?)', (ver, note))


def init_db():
    """建表 + 建视图 + 写入默认配置（不覆盖已有）+ WAL + 迁移"""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.execute('PRAGMA journal_mode=WAL')   # 两人共用：多读单写，读不阻塞写
        _apply_migrations(conn)
        conn.executescript('''
        DROP VIEW IF EXISTS v_debt;
        CREATE VIEW v_debt AS
        SELECT agg.month, agg.project, agg.cls,
               agg.notice_amount, agg.pay_amount,
               CASE WHEN agg.cls = '机械' AND ms.amount IS NOT NULL THEN ms.amount
                    ELSE agg.stat_settle END AS stat_settle,
               agg.stat_pay,
               CASE WHEN agg.cls = '机械' AND ms.amount IS NOT NULL THEN ms.amount
                    ELSE agg.stat_settle END - agg.stat_pay AS debt
        FROM (
          SELECT substr(pn.单据日期,1,7) AS month,
                 pn.stat_name AS project,
                 pn.biz_class AS cls,
                 SUM(pn.审批金额) AS notice_amount,
                 COALESCE(SUM(pfp.pay_amount), 0) AS pay_amount,
                 SUM(COALESCE(pn.计入统计结算, pn.审批金额)) AS stat_settle,
                 SUM(COALESCE(pn.计入统计付款, COALESCE(pfp.pay_amount, 0))) AS stat_pay
          FROM pay_notice pn
          LEFT JOIN (SELECT notice_id, SUM(pay_amount) AS pay_amount
                     FROM pay_flow WHERE voided = 0 GROUP BY notice_id) pfp
            ON pfp.notice_id = pn.id
          WHERE pn.biz_class IN ('辅材', '机械') AND pn.deleted = 0
          GROUP BY substr(pn.单据日期,1,7), pn.stat_name, pn.biz_class
        ) agg
        LEFT JOIN mach_settle ms ON ms.project = agg.project AND ms.month = agg.month;
        ''')
        for k, v in DEFAULT_CONFIG.items():
            conn.execute('INSERT OR IGNORE INTO config(key, value, note) VALUES(?,?,?)',
                         (k, json.dumps(v, ensure_ascii=False), ''))
        # 默认账号（首次初始化 seed；之后可增删、可改密/改 i8 绑定，见 config 页用户管理）
        # admin=材料科负责人（i8=SCY980803 无密码）；kezhang=科长（i8=CSM880909）
        from auth import hash_password, obfuscate_i8_password
        conn.execute('INSERT OR IGNORE INTO users(username, password_hash, display_name, i8_account, i8_password) VALUES(?,?,?,?,?)',
                     ('admin', hash_password('123456'), '管理员', 'SCY980803', ''))
        conn.execute('INSERT OR IGNORE INTO users(username, password_hash, display_name, i8_account, i8_password) VALUES(?,?,?,?,?)',
                     ('kezhang', hash_password('123456'), '科长', 'CSM880909', obfuscate_i8_password('090988')))
        # 兼容旧库：admin 已存在但缺 i8 绑定，幂等补上 SCY980803（仅当为空时，不覆盖用户后续改动）
        conn.execute("UPDATE users SET i8_account='SCY980803' WHERE username='admin' AND (i8_account IS NULL OR i8_account='')")
        conn.commit()
    finally:
        conn.close()


def get_config(key, default=None):
    """读配置：库内没有 → 回退 DEFAULT_CONFIG（唯一真源）→ 仍没有才用 default。
    **调用方不要再传业务默认值**（历史坑：db.py / export_runner / sfjc_extract 各写一份，
    weld_keywords 两处漏"焊锡丝"，导致新环境初始化即口径回退）"""
    conn = get_conn()
    try:
        row = conn.execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()
        if row is None:
            return DEFAULT_CONFIG.get(key, default)
        return json.loads(row['value'])
    finally:
        conn.close()


def set_config(key, value, note=''):
    conn = get_conn()
    try:
        conn.execute('INSERT INTO config(key, value, note) VALUES(?,?,?) '
                     'ON CONFLICT(key) DO UPDATE SET value=excluded.value, note=excluded.note',
                     (key, json.dumps(value, ensure_ascii=False), note))
        conn.commit()
    finally:
        conn.close()


# ================= 用户（用户名+密码鉴权，支持人员更迭）=================
def verify_user(username, password):
    """校验用户名密码，成功返回 {'id','username','display_name'}，失败返回 None。"""
    from auth import verify_password
    conn = get_conn()
    try:
        row = conn.execute(
            'SELECT id, username, password_hash, display_name, is_active FROM users WHERE username=?',
            (username,)).fetchone()
        if row is None or not row['is_active']:
            return None
        if verify_password(password, row['password_hash']):
            return {'id': row['id'], 'username': row['username'],
                    'display_name': row['display_name'] or row['username']}
        return None
    finally:
        conn.close()


def list_users():
    """列出全部用户（不含密码哈希；i8 密码不返回明文，仅返回是否已设置）。"""
    conn = get_conn()
    try:
        rows = [dict(r) for r in conn.execute(
            'SELECT id, username, display_name, is_active, created_at, i8_account, i8_password FROM users ORDER BY id')]
        for r in rows:
            r['i8_has_password'] = bool(r.get('i8_password'))
            r.pop('i8_password', None)
        return rows
    finally:
        conn.close()


def ensure_project(name, is_small='否', conn=None, full_name=None):
    """按 name(仓库名)/full_name(全名)/aliases 三维匹配建档（upsert），返回 project_id。
    - name：主匹配键（仓库名），建档时必填
    - full_name：次匹配键（全名，可选），建档时写入；命中且本行 full_name 为空时补写
    - aliases：兜底匹配（名字作为别名）
    匹配优先级：name 精确 > full_name 精确 > aliases 包含。传入 conn 时共用事务。"""
    own = conn is None
    if own:
        conn = get_conn()
    try:
        fn = (full_name or '').strip()
        row = conn.execute('SELECT id, full_name FROM projects WHERE name=?', (name,)).fetchone()
        if row is None and fn:
            row = conn.execute('SELECT id, full_name FROM projects WHERE full_name=?', (fn,)).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT id, full_name FROM projects WHERE INSTR(aliases, ?) > 0 "
                "OR (? != '' AND INSTR(aliases, ?) > 0) ORDER BY id LIMIT 1",
                ('|' + name + '|', fn, '|' + fn + '|')).fetchone()
        if row:
            if fn and not (row['full_name'] or ''):
                conn.execute('UPDATE projects SET full_name=? WHERE id=?', (fn, row['id']))
            return row['id']
        cur = conn.execute('INSERT INTO projects(name, is_small, full_name) VALUES(?,?,?)',
                           (name, is_small, fn))
        if own:
            conn.commit()
        return cur.lastrowid
    finally:
        if own:
            conn.close()


if __name__ == '__main__':
    init_db()
    print('数据库初始化完成:', DB_PATH)
