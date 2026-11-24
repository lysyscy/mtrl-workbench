import * as schema from 'valibot';
import { ApiError, body, record, requestFile, requestJson } from './api';
import { saveBlob } from './flow-api';

export type ItemCategory = 'equipment' | 'turnover';
export type InventoryCategory = 'tool' | 'turnover';
export type Scope = 'current_asset' | 'fixed_asset' | 'off_book';
export type RentalFlag = 'yes' | 'no' | 'pending';
export type Status = 'in_use' | 'damaged' | 'pending_scrap';
export type SyncStatus = 'synced' | 'pending' | 'conflict' | 'failed' | 'not_applicable';
export type Pending = 'none' | 'transfer_attribution' | 'new_purchase_start' | 'scrap_stop';
export type Billing = 'normal' | 'skip_month' | 'stopped' | 'blank';
export type Choice =
  'this_month' | 'next_month' | 'from_project' | 'to_project' | 'stop_this_month' | 'charge_this_month';

const text = schema.string();
const id = schema.pipe(schema.number(), schema.integer(), schema.minValue(1));
const count = schema.pipe(schema.number(), schema.integer(), schema.minValue(0));
const nullableText = schema.nullable(text);
const itemCategory = schema.picklist(['equipment', 'turnover']);
const syncStatus = schema.picklist(['synced', 'pending', 'conflict', 'failed', 'not_applicable']);
const inventoryItem = schema.object({
  id,
  category: schema.picklist(['tool', 'turnover']),
  sort_order: schema.number(),
  name: text,
  spec: nullableText,
  unit: nullableText,
  unit_price: nullableText,
  book_qty: text,
  book_amount: nullableText,
  count_qty: text,
  count_amount: nullableText,
  diff_qty: nullableText,
  diff_amount: nullableText,
  diff_reason: nullableText,
  is_active: schema.boolean(),
  source_row: nullableText,
  created_at: text,
  updated_at: text,
  created_by: text,
  updated_by: text,
});
export type InventoryItem = schema.InferOutput<typeof inventoryItem>;

const equipmentItem = schema.object({
  id,
  code: text,
  item_category: itemCategory,
  name: text,
  spec: nullableText,
  unit: nullableText,
  quantity: text,
  purchase_date: nullableText,
  purchase_date_text: nullableText,
  purchase_project: text,
  purchase_project_id: schema.nullable(id),
  purchase_project_disp: nullableText,
  purchase_project_custom: nullableText,
  purchase_price: nullableText,
  current_project: text,
  current_project_id: schema.nullable(id),
  current_project_disp: nullableText,
  current_project_custom: nullableText,
  status: schema.picklist(['in_use', 'damaged', 'pending_scrap', 'scrapped']),
  asset_scope: schema.picklist(['current_asset', 'fixed_asset', 'off_book']),
  in_rental: schema.picklist(['yes', 'no', 'pending']),
  remark: nullableText,
  i8_sync_status: syncStatus,
  i8_sync_message: nullableText,
  i8_snapshot_json: nullableText,
  source_info: nullableText,
  rental_source_row: nullableText,
  inventory_source_row: nullableText,
  inventory_item_id: schema.nullable(id),
  inventory_name: nullableText,
  inventory_book_qty: nullableText,
  inventory_count_qty: nullableText,
  scrap_date: nullableText,
  scrap_reason: nullableText,
  created_at: text,
  updated_at: text,
  created_by: text,
  updated_by: text,
});
export type EquipmentItem = schema.InferOutput<typeof equipmentItem>;

const equipmentTransfer = schema.object({
  id,
  equipment_id: id,
  item_category: itemCategory,
  from_project: text,
  from_project_id: schema.nullable(id),
  from_project_disp: nullableText,
  from_project_custom: nullableText,
  to_project: text,
  to_project_id: schema.nullable(id),
  to_project_disp: nullableText,
  to_project_custom: nullableText,
  transfer_date: nullableText,
  quantity: text,
  remark: nullableText,
  i8_sync_status: syncStatus,
  i8_sync_message: nullableText,
  i8_conflict_json: nullableText,
  rental_month: nullableText,
  rental_attribution: text,
  created_at: text,
  created_by: text,
});
export type EquipmentTransfer = schema.InferOutput<typeof equipmentTransfer>;

const equipmentScrap = schema.object({
  id,
  equipment_id: id,
  item_category: itemCategory,
  scrap_date: text,
  original_project: text,
  original_project_id: schema.nullable(id),
  original_project_disp: nullableText,
  original_project_custom: nullableText,
  quantity: text,
  purchase_price: nullableText,
  reason: nullableText,
  rental_stop_status: text,
  created_at: text,
  created_by: text,
});
export type EquipmentScrap = schema.InferOutput<typeof equipmentScrap>;

const rentalMonth = schema.object({
  id,
  month: text,
  status: schema.picklist(['draft', 'confirmed']),
  confirmed_at: nullableText,
  confirmed_by: nullableText,
  created_at: text,
  updated_at: text,
});
export type RentalMonth = schema.InferOutput<typeof rentalMonth>;

const rentalLine = schema.object({
  id,
  month: text,
  project_name: text,
  project_id: schema.nullable(id),
  project_disp: nullableText,
  project_custom: nullableText,
  project_sort_order: schema.number(),
  row_sort_order: schema.number(),
  equipment_id: schema.nullable(id),
  name: text,
  spec: nullableText,
  unit: nullableText,
  quantity: text,
  original_value: nullableText,
  custom_unit_price: nullableText,
  unit_price: nullableText,
  amount: nullableText,
  category_label: text,
  distribution_note: nullableText,
  billing_status: schema.picklist(['normal', 'skip_month', 'stopped', 'blank']),
  pending_action_type: schema.picklist(['none', 'transfer_attribution', 'new_purchase_start', 'scrap_stop']),
  pending_meta_json: nullableText,
  source_row: nullableText,
  created_at: text,
  updated_at: text,
});
export type RentalLine = schema.InferOutput<typeof rentalLine>;

const identityFields = { code: text, name: text, spec: nullableText, unit: nullableText };
const transferRow = schema.object({ ...equipmentTransfer.entries, ...identityFields });
const scrapRow = schema.object({ ...equipmentScrap.entries, ...identityFields });
export type TransferRow = schema.InferOutput<typeof transferRow>;
export type ScrapRow = schema.InferOutput<typeof scrapRow>;
export type Preview = Pick<EquipmentItem, 'name' | 'quantity' | 'item_category'> & { purchase_date: string };
export type EquipmentPatch = Partial<
  Pick<
    EquipmentItem,
    | 'name'
    | 'spec'
    | 'unit'
    | 'purchase_project'
    | 'purchase_project_id'
    | 'purchase_project_custom'
    | 'purchase_date'
    | 'purchase_price'
    | 'asset_scope'
    | 'in_rental'
    | 'remark'
  > & { status: Status }
>;
export type Create = EquipmentPatch &
  Preview & {
    expected_codes: string[];
    current_project?: string;
    current_project_id?: number | null;
    current_project_custom?: string | null;
    target_month?: string;
    custom_unit_price?: string | null;
  };
export type InventoryValues = Pick<InventoryItem, 'name' | 'category' | 'book_qty' | 'count_qty'> &
  Partial<Pick<InventoryItem, 'spec' | 'unit' | 'unit_price' | 'diff_qty' | 'diff_reason' | 'sort_order'>>;
export type RentPatch = Partial<
  Pick<RentalLine, 'quantity' | 'custom_unit_price' | 'billing_status' | 'distribution_note'>
>;
const ids = schema.array(id);
const codes = schema.array(schema.pipe(text, schema.nonEmpty()));
const preview = schema.object({ codes: schema.pipe(codes, schema.nonEmpty()) });
const syncResults = schema.array(schema.object({ id, status: syncStatus, message: nullableText }));
const rentGroup = schema.object({
  project_id: schema.nullable(id),
  project_name: text,
  lines: schema.array(rentalLine),
  subtotal: nullableText,
});
export type RentGroup = schema.InferOutput<typeof rentGroup>;
const projectOption = schema.object({ id, disp: text, status: text, phid: text, warehouse_name: nullableText });
export type EquipmentProjectOption = schema.InferOutput<typeof projectOption>;
const monthly = schema.object({
  month: text,
  status: rentalMonth.entries.status,
  pending_count: count,
  projects: schema.array(rentGroup),
  grand_total: nullableText,
  printable_project_count: count,
});
type Filters = { item_category?: ItemCategory | undefined; project?: string; keyword?: string };
type Retry = { equipment_ids: number[]; transfer_ids: number[] };
const root = '/api/m16';
function url(path: string, params: object = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params))
    if (value !== undefined && value !== '') query.set(key, String(value));
  return root + path + (query.size ? '?' + query : '');
}
function validationMessage(detail: unknown) {
  if (typeof detail === 'string') return detail;
  if (!Array.isArray(detail)) return '';
  return detail
    .flatMap((issue: unknown) => {
      if (!record(issue) || typeof issue.msg !== 'string') return [];
      const field = Array.isArray(issue.loc) ? issue.loc.filter((x) => x !== 'body').join('.') : '';
      return [field ? field + '：' + issue.msg : issue.msg];
    })
    .join('；');
}

type ResponseSchema = schema.GenericSchema;
async function checked<S extends ResponseSchema>(
  contract: S,
  path: string,
  init?: RequestInit
): Promise<schema.InferOutput<S>> {
  try {
    const parsed = schema.safeParse(contract, await requestJson(path, init));
    if (!parsed.success) throw new ApiError('台账回执缺少有效数据，请刷新核对。', 0, 'invalid_response');
    return parsed.output;
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      const message = validationMessage(error.detail);
      if (message) throw new ApiError(message, 422, error.code, error.detail);
    }
    throw error;
  }
}
const get = <S extends ResponseSchema>(contract: S, path: string, params?: object) =>
  checked(contract, url(path, params));
const write = <S extends ResponseSchema>(contract: S, path: string, method: string, values: object) =>
  checked(contract, url(path), { method, ...body(values) });

export const equipmentApi = {
  projectOptions: () => get(schema.object({ items: schema.array(projectOption) }), '/project-options'),
  preview: (v: Preview) => write(preview, '/equipment/preview', 'POST', v),
  previewGet: (v: Preview) => get(preview, '/equipment/preview', v),
  create: (v: Create) =>
    write(
      schema.object({
        codes: preview.entries.codes,
        equipment: schema.pipe(schema.array(equipmentItem), schema.nonEmpty()),
        inventory_item: schema.nullable(inventoryItem),
        rental_line_ids: ids,
        i8_sync: syncResults,
      }),
      '/equipment',
      'POST',
      v
    ),
  list: (
    f: Filters & {
      asset_scope?: Scope;
      in_rental?: RentalFlag;
      sync_issue_only?: boolean;
      include_scrapped?: boolean;
      status?: EquipmentItem['status'];
    }
  ) =>
    get(
      schema.object({
        items: schema.array(equipmentItem),
        summary: schema.object({
          active_count: count,
          pending_sync_count: count,
          conflict_count: count,
          pending_rental_count: count,
        }),
      }),
      '/equipment',
      f
    ),
  detail: (id: number, month?: string) =>
    get(
      schema.object({
        equipment: equipmentItem,
        transfers: schema.array(transferRow),
        scrap: schema.nullable(scrapRow),
        inventory_item: schema.nullable(inventoryItem),
        rental_lines: schema.array(rentalLine),
        i8_sync: schema.object({ status: syncStatus, message: nullableText, snapshot_json: nullableText }),
      }),
      '/equipment/' + id,
      { month }
    ),
  update: (id: number, v: EquipmentPatch) => write(equipmentItem, '/equipment/' + id, 'PATCH', v),
  transfers: (f: Filters & { sync_status?: SyncStatus }) =>
    get(schema.object({ items: schema.array(transferRow) }), '/transfers', f),
  transfer: (v: {
    equipment_ids: number[];
    expected_from_projects?: Record<number, string>;
    to_project_id: number | null;
    to_project_custom: string | null;
    transfer_date: string;
    remark?: string | null;
  }) =>
    write(
      schema.object({
        equipment_ids: ids,
        transfers: schema.array(equipmentTransfer),
        rental_line_ids: ids,
        i8_sync: syncResults,
      }),
      '/transfers',
      'POST',
      v
    ),
  scraps: (f: Filters) => get(schema.object({ items: schema.array(scrapRow) }), '/scraps', f),
  scrap: (
    v: ({ equipment_id: number } | { equipment_ids: number[] }) & {
      scrap_date: string;
      reason?: string | null;
    }
  ) =>
    write(
      schema.object({ equipment_ids: ids, scraps: schema.array(equipmentScrap), rental_line_ids: ids }),
      '/scraps',
      'POST',
      v
    ),
  issues: () =>
    get(
      schema.object({ equipment: schema.array(equipmentItem), transfers: schema.array(equipmentTransfer) }),
      '/i8-sync/issues'
    ),
  retry: (v: Retry) =>
    write(schema.object({ equipment: syncResults, transfers: syncResults }), '/i8-sync/retry', 'POST', v),
  rental: (month: string, project?: string) => get(monthly, '/rental', { month, project }),
  patchLine: (id: number, v: RentPatch) => write(rentalLine, '/rental/lines/' + id, 'PATCH', v),
  resolve: (id: number, choice: Choice) =>
    write(rentalLine, '/rental/lines/' + id + '/resolve', 'POST', { choice }),
  reorder: (month: string, project_id: number | null, project_name: string, ordered_line_ids: number[]) =>
    write(schema.object({ ordered_line_ids: ids }), '/rental/reorder', 'PUT', {
      month,
      project_id,
      project_name,
      ordered_line_ids,
    }),
  confirm: (month: string) => write(rentalMonth, '/rental/confirm', 'POST', { month }),
  inventory: (category?: InventoryCategory) =>
    get(
      schema.object({
        items: schema.array(inventoryItem),
        book_amount: nullableText,
        count_amount: nullableText,
      }),
      '/inventory',
      {
        category,
      }
    ),
  addInventory: (v: InventoryValues) => write(inventoryItem, '/inventory', 'POST', v),
  editInventory: (id: number, v: Partial<Omit<InventoryValues, 'category'>>) =>
    write(inventoryItem, '/inventory/' + id, 'PATCH', v),
};
export function exportEquipment(kind: 'distribution' | 'inventory'): Promise<void>;
export function exportEquipment(kind: 'rental', month: string): Promise<void>;
export async function exportEquipment(kind: 'distribution' | 'inventory' | 'rental', month?: string) {
  const { blob, filename } = await requestFile(url('/export/' + kind, { month }));
  saveBlob(blob, filename);
}
