# 单端点类型生成：未采用的实验补丁

仅临时源码副本验证；未应用原仓。最终复核：生成器peer仅typescript ^5.x，临时树使用5.9.3；消费者用项目TS7编译通过不代表生成器TS7兼容。原项目直接接入暂缓，不用peer覆盖或第二工具工程强行接入。openapi-typescript固定7.13.0（MIT），运行reader与枚举收窄保留。正式接入还须固定开发依赖/锁并接简单生成命令，不能仅复制此生成文件。临时消费者严格TS7编译通过；schema ord改string导致api/ledger/process等真实消费者报错，随后恢复。初次临时模块解析失败已修正，不是产品兼容失败。尚未运行HTTP形状比对。

## 离线导出核心

在backend导入路径下执行；脚本还需标准json导入。真实router元数据，不启动应用/生命周期、不调用endpoint，不需要数据库或凭据。

```python
from fastapi.openapi.utils import get_openapi
from app.mod01_projects.router import router
routes = [r for r in router.routes if r.path == '/api/m01/projects' and r.methods == {'GET'}]
assert len(routes) == 1
print(json.dumps(get_openapi(title='Project read contract', version='1', routes=routes), ensure_ascii=False, sort_keys=True, indent=2))
```

使用官方CLI对导出文件生成project-api.d.ts（两次输出SHA256相同：fc74aece620993bacf1e8cba0ffd8a34e2bd01bf6be3626d6951b9c059ad8e04）。

## 已验证消费者补丁

```diff
--- a/apps/frontend/src/api.ts
+++ b/apps/frontend/src/api.ts
@@ -103,7 +103,8 @@
   return { id: me.id, account: me.account, name: me.name, role: me.role, ui_scale_css: me.ui_scale_css, theme: typeof me.theme === 'string' ? me.theme : '', ui_scale: typeof me.ui_scale === 'string' ? me.ui_scale : '' };
 }
 
-export interface Project { id: number; name_full: string; warehouse_name: string | null; disp: string; project_type: 'normal' | 'shell' | 'small'; status: 'active' | 'archived'; ord: number; phid: string }
+import type { Project } from './project-wire';
+export type { Project } from './project-wire';
 export function projectLabel(project: Project): string { return project.disp.trim() || '未设置展示名'; }
 export function readProjects(value: unknown): Project[] {
   if (!Array.isArray(value)) throw new ApiError('项目列表不完整，请重试；仍失败请联系维护人员。');
--- a/apps/frontend/src/projects.tsx
+++ b/apps/frontend/src/projects.tsx
@@ -13,7 +13,7 @@
 import type { Identity, Project } from './api';
 import { DialogContents, useDialogClose } from './dialog-close';
 
-type ArchiveProject = Project & { parent_shell_id: number | null; match_keywords: string[]; is_placeholder: boolean };
+import type { ArchiveProject } from './project-wire';
 type Candidate = { id: number; disp: string; warehouse_name: string; status: string; is_placeholder: boolean };
 type Pending = { full_name: string; warehouse_name?: string; candidates?: Candidate[]; warehouses?: string[]; reason?: string };
 type PendingList = { items: Pending[]; source: { at?: string; target?: string }; dropped_items?: { full_name: string; why_text: string }[] };
--- /dev/null
+++ b/apps/frontend/src/project-api.d.ts
@@ -0,0 +1,112 @@
+export interface paths {
+    "/api/m01/projects": {
+        parameters: {
+            query?: never;
+            header?: never;
+            path?: never;
+            cookie?: never;
+        };
+        /** List Projects */
+        get: operations["list_projects_api_m01_projects_get"];
+        put?: never;
+        post?: never;
+        delete?: never;
+        options?: never;
+        head?: never;
+        patch?: never;
+        trace?: never;
+    };
+}
+export type webhooks = Record<string, never>;
+export interface components {
+    schemas: {
+        /** HTTPValidationError */
+        HTTPValidationError: {
+            /** Detail */
+            detail?: components["schemas"]["ValidationError"][];
+        };
+        /** ProjectOut */
+        ProjectOut: {
+            /** Disp */
+            disp: string;
+            /** Id */
+            id: number;
+            /**
+             * Is Placeholder
+             * @default false
+             */
+            is_placeholder: boolean;
+            /** Match Keywords */
+            match_keywords?: string[];
+            /** Name Full */
+            name_full: string;
+            /** Ord */
+            ord: number;
+            /** Parent Shell Id */
+            parent_shell_id?: number | null;
+            /** Phid */
+            phid: string;
+            /** Project Type */
+            project_type: string;
+            /** Status */
+            status: string;
+            /** Warehouse Name */
+            warehouse_name?: string | null;
+        };
+        /** ValidationError */
+        ValidationError: {
+            /** Context */
+            ctx?: Record<string, never>;
+            /** Input */
+            input?: unknown;
+            /** Location */
+            loc: (string | number)[];
+            /** Message */
+            msg: string;
+            /** Error Type */
+            type: string;
+        };
+    };
+    responses: never;
+    parameters: never;
+    requestBodies: never;
+    headers: never;
+    pathItems: never;
+}
+export type $defs = Record<string, never>;
+export interface operations {
+    list_projects_api_m01_projects_get: {
+        parameters: {
+            query?: {
+                /** @description active / archived / all（**默认在建**） */
+                status?: string;
+                /** @description 按全名 / 仓库名 / 展示名模糊匹配 */
+                keyword?: string;
+            };
+            header?: never;
+            path?: never;
+            cookie?: never;
+        };
+        requestBody?: never;
+        responses: {
+            /** @description Successful Response */
+            200: {
+                headers: {
+                    [name: string]: unknown;
+                };
+                content: {
+                    "application/json": components["schemas"]["ProjectOut"][];
+                };
+            };
+            /** @description Validation Error */
+            422: {
+                headers: {
+                    [name: string]: unknown;
+                };
+                content: {
+                    "application/json": components["schemas"]["HTTPValidationError"];
+                };
+            };
+        };
+    };
+}
--- /dev/null
+++ b/apps/frontend/src/project-wire.ts
@@ -0,0 +1,4 @@
+import type { components } from './project-api';
+type Wire = Required<components['schemas']['ProjectOut']>;
+export type ArchiveProject = Omit<Wire, 'project_type' | 'status'> & { project_type: 'normal' | 'shell' | 'small'; status: 'active' | 'archived' };
+export type Project = Pick<ArchiveProject, 'id' | 'name_full' | 'warehouse_name' | 'disp' | 'project_type' | 'status' | 'ord' | 'phid'>;
```
