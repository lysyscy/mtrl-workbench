import { ApiError, record, requestJson } from './api';
import { body } from './notices-api';

export async function loadContractExport(kind: 'ordinary' | 'print', selection: number[] | string[], signal: AbortSignal) {
  const value = await requestJson(`/api/m11/${kind === 'print' ? 'print-export' : 'export'}`, {
    method: 'POST', ...body(kind === 'print' ? { projects: selection } : { ids: selection }), signal,
  });
  if (!record(value) || value.ok !== true || typeof value.filename !== 'string' || !value.filename.endsWith('.xlsx') ||
      /[\\/:\x00-\x1f]/.test(value.filename) || typeof value.content_b64 !== 'string' || !value.content_b64) {
    throw new ApiError('导出文件不完整，请重试；仍失败请联系维护人员。');
  }
  let bytes: Uint8Array<ArrayBuffer>;
  try { bytes = Uint8Array.from(atob(value.content_b64), char => char.charCodeAt(0)); }
  catch { throw new ApiError('导出文件不完整，请重试；仍失败请联系维护人员。'); }
  if (bytes.length < 4 || bytes[0] !== 0x50 || bytes[1] !== 0x4b || bytes[2] !== 3 || bytes[3] !== 4) {
    throw new ApiError('导出文件不完整，请重试；仍失败请联系维护人员。');
  }
  if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
  return { blob: new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), filename: value.filename };
}
