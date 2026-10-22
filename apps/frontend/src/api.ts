export class ApiError extends Error {
  constructor(message: string, public status = 0) { super(message); }
}

async function requestResponse(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response;
  try { response = await fetch(path, { ...init, credentials: 'same-origin', headers: { Accept: 'application/json', ...init.headers } }); }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('连接失败，请检查网络后重试。');
  }
  if (init.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  if (response.status === 401) {
    window.dispatchEvent(new Event('session-lost'));
    throw new ApiError('登录已失效，请重新登录后重试。', 401);
  }
  if (response.status === 403) throw new ApiError('当前无法访问，请联系管理员核对权限或访问范围。', 403);
  return response;
}

async function jsonResult(response: Response): Promise<unknown> {
  let data: unknown;
  try { data = await response.json(); }
  catch { throw new ApiError('读取结果不完整，请重试；仍失败请联系维护人员。', response.status); }
  if (!response.ok || (record(data) && data.ok === false)) {
    const message = record(data) && typeof data.message === 'string' ? data.message : '读取失败，请重试；仍失败请联系维护人员。';
    throw new ApiError(message, response.status);
  }
  return data;
}

export async function requestJson(path: string, init: RequestInit = {}): Promise<unknown> {
  return jsonResult(await requestResponse(path, init));
}

export async function requestFile(path: string, signal?: AbortSignal): Promise<{ blob: Blob; filename: string }> {
  const response = await requestResponse(path, signal ? { signal } : {});
  if (!response.ok || response.headers.get('content-type')?.includes('json')) {
    await jsonResult(response);
    throw new ApiError('导出未生成文件，请核对范围后重试。');
  }
  const encoded = response.headers.get('X-Export-Filename');
  if (!encoded) throw new ApiError('导出文件名不完整，请联系维护人员。');
  let filename: string;
  try { filename = decodeURIComponent(encoded); }
  catch { throw new ApiError('导出文件名不完整，请联系维护人员。'); }
  if (!filename || /[\\/:]/.test(filename)) throw new ApiError('导出文件名不完整，请联系维护人员。');
  return { blob: await response.blob(), filename };
}

export function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export interface Identity { id: number; account: string; name: string; role: 'admin' | 'user'; ui_scale_css: string }
export function readIdentity(value: unknown): Identity | null {
  if (record(value) && value.me === null) return null;
  const me = record(value) ? value.me : undefined;
  if (!record(me) || !Number.isInteger(me.id) || typeof me.id !== 'number' || typeof me.account !== 'string' || !me.account || typeof me.name !== 'string' || (me.role !== 'admin' && me.role !== 'user') || typeof me.ui_scale_css !== 'string' || !/^1(?:\.\d+)?$/.test(me.ui_scale_css)) {
    throw new ApiError('账号信息不完整，请重新登录；仍失败请联系维护人员。');
  }
  return { id: me.id, account: me.account, name: me.name, role: me.role, ui_scale_css: me.ui_scale_css };
}

export interface Project { id: number; name_full: string; warehouse_name: string | null; disp: string; project_type: 'normal' | 'shell' | 'small'; status: 'active' | 'archived'; ord: number; phid: string }
export function readProjects(value: unknown): Project[] {
  if (!Array.isArray(value)) throw new ApiError('项目列表不完整，请重试；仍失败请联系维护人员。');
  return value.map((row: unknown) => {
    if (!record(row) || typeof row.id !== 'number' || !Number.isInteger(row.id) || typeof row.name_full !== 'string' || (row.warehouse_name !== null && typeof row.warehouse_name !== 'string') || typeof row.disp !== 'string' || !['normal','shell','small'].includes(String(row.project_type)) || !['active','archived'].includes(String(row.status)) || typeof row.ord !== 'number' || typeof row.phid !== 'string') throw new ApiError('项目列表不完整，请重试；仍失败请联系维护人员。');
    return { id: row.id, name_full: row.name_full, warehouse_name: row.warehouse_name, disp: row.disp, project_type: row.project_type as Project['project_type'], status: row.status as Project['status'], ord: row.ord, phid: row.phid };
  });
}
