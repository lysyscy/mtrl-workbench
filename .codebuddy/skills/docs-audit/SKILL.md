---
name: docs-audit
description: 整理或审查本仓文档的用途、重复口径、过期指针和历史读取路径；用户要求文档减负、合并、归档或检查组织时使用。普通单篇校对不触发整仓盘点。
---

# 文档审查与整理

通用资料维护与实施核验按AGENTS条件读取个人文档维护约定及implement-solo-spec“验证与失败处理”；本件只持有本仓分类、检查入口与整理适配。项目核验绑定 = docs/agents/workflow.md；分层、命名与落点 = README.md §二/四/七；治理关系 = docs/guides/document-governance.md。

## 执行

1. 按当前授权和现行入口定位本仓受影响资料；仅需完整分布时运行 scripts/doc_inventory.py，不把目录盘点当日常闸门。
2. 按用途分类，参考 references/taxonomy.md。区分现行要求、机器输入、索引、过程和恢复证据；日期、体量及零引用都不能单独证明无用。
3. 用 docs/guides/document-governance.md、README.md 和项目检查定位主人与使用者；整理、同步活引用和历史保留按个人文档维护约定执行。归档例外回 docs/guides/work-records.md，业务裁定回delivery，保存授权回docs/agents/workflow.md。
4. 选择本仓现有相关检查；颜色和机器范围读法见 references/rulers.md。结果在原票或改动说明承载，不生成第二份状态或阅读日志；未知耗时不补估算。

## 完成标准

维护完成条件回个人文档维护约定；本仓额外核文档落点、实际活引用、D件只追加例外及所选机器输入，未验项据实保留。

## 按需资源

- scripts/doc_inventory.py：分布、预算与重复的只读盘点；需要完整分布才跑，不是日常闸门。
- scripts/orphan_scan.py：保守文本引用线索，历史引用也会计入；旧memory兼容件可能归history桶，新开发正文由ops前缀归现行。分类和计数均不决定删除或证明无用途。
- references/taxonomy.md：用途分类与病因提示。
- references/rulers.md：检查结果读法，核验选择仍回流程主人。
