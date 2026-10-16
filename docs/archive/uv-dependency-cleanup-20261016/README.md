# uv 依赖审计与迁移归档

状态：已结项并归档（2026-10-16）。本轮依赖精简、隔离验证、本机同步和用户授权服务加载均已完成；此前收尾漏做归档，本次补齐。

现行依赖由 `backend/pyproject.toml`、`backend/uv.lock` 持有，操作方法在 `docs/guides/deployment.md` §六。本目录仅供历史追溯，其中脚本包含当时绝对路径、缓存及服务操作，不能作为当前运行入口直接执行。

原位置 `.scratch/uv-dependency-cleanup/`；初次审计的三个文件原位于 `.scratch/local/`。除下述四件可逆提交保护调整外，原文字节未改；逐件原路径和 SHA-256 见 manifest.json；Git基线不包含当时未提交修改，不单独作为原件恢复证明。

结果与未验边界见 evidence.md，检查原始输出保留在本目录；初次扫描见 initial-audit/。源码改动仍在工作区，未提交或推送；未执行完整业务回归、漏洞数据库扫描、真实业务操作或实体打印。这些未验边界不属于此次依赖收尾的未完成验收项。

提交前编码核验（2026-10-16）：cleanup.ps1、find_module_owner.ps1仅补UTF-8 BOM，以满足仓库PowerShell字节保护。manifest同时保留source_sha256及当前归档sha256；去掉开头EF BB BF即可逐字节重建原件。不执行这些历史脚本。

提交钩子同时要求两份initial-audit Python脚本具有模块说明，本次仅在首行追加归档用途docstring；manifest保留source_sha256，移除首行可重建原件。原始.log及审计文本通过目录.gitattributes保持原始字节，不格式化历史输出。
