import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Tree from 'antd/es/tree';
import { useMemo, useRef, useState } from 'react';
import { useGridFilterDisplay } from 'ag-grid-react';
import type { CustomFilterDisplayProps } from 'ag-grid-react';
import type { ColDef, DoesFilterPassParams } from 'ag-grid-community';
import { checkedValueFilterNodes, compareFilterValues, searchValueFilterTree, toggleValueFilter, valueFilterCandidates, valueFilterPasses, valueFilterTree } from './grid-value-filter-model';
import type { FilterValue, ValueFilterKind, ValueFilterModel, ValueFilterNode } from './grid-value-filter-model';

export interface ValueFilterOptions<T> {
  kind: ValueFilterKind;
  value: (row: T) => FilterValue;
  format?: (value: FilterValue) => string;
  includeCandidate?: (row: T) => boolean;
  keepVisible?: (row: T) => boolean;
}
type FilterProps<T> = CustomFilterDisplayProps<T, unknown, ValueFilterModel> & { valueFilter: ValueFilterOptions<T> };

function ValueFilter<T>({ model, onModelChange, api, column, valueFilter: options }: FilterProps<T>) {
  const [search, setSearch] = useState(''), [revision, setRevision] = useState(0);
  const [expanded, setExpanded] = useState<string[] | null>(null);
  const close = useRef<(() => void) | undefined>(undefined);
  useGridFilterDisplay({ afterGuiAttached: params => { close.current = params?.hidePopup; setSearch(''); setRevision(n => n + 1); },
    onNewRowsLoaded: () => setRevision(n => n + 1), onAnyFilterChanged: () => setRevision(n => n + 1) });
  const nodes = useMemo(() => {
    const values: FilterValue[] = [];
    api.forEachLeafNode(node => { if (node.data && (options.includeCandidate?.(node.data) ?? true)) values.push(options.value(node.data)); });
    return valueFilterTree(valueFilterCandidates(values, options.kind, options.format), options.kind);
  }, [api, options, revision]);
  const visible = useMemo(() => searchValueFilterTree(nodes, search), [nodes, search]);
  const checked = useMemo(() => checkedValueFilterNodes(nodes, model), [nodes, model]);
  const expandedKeys = useMemo(() => {
    if (!search.trim() && expanded !== null) return expanded;
    const keys: string[] = [];
    const visit = (node: ValueFilterNode) => { if (node.children?.length) { keys.push(node.key); node.children.forEach(visit); } };
    (search.trim() ? visible : nodes).forEach(visit);
    return keys;
  }, [nodes, visible, search, expanded]);
  const selected = model?.values ?? [];
  function sort(direction: 'asc' | 'desc') { api.applyColumnState({ state: [{ colId: column.getColId(), sort: direction }], defaultState: { sort: null } }); }
  return <div className="grid-value-filter ag-custom-component-popup" role="group" aria-label={`${column.getColDef().headerName ?? column.getColId()}筛选`}>
    {options.kind === 'number' && <div className="grid-value-filter-sort"><Button onClick={() => sort('asc')}>数值升序</Button><Button onClick={() => sort('desc')}>数值降序</Button></div>}
    <Input aria-label="搜索筛选候选" placeholder="搜索候选" value={search} allowClear onChange={e => setSearch(e.target.value)} />
    <div className="grid-value-filter-selected">已选 <span>{selected.length ? selected.length : ''}</span></div>
    {visible.length ? <Tree<ValueFilterNode> className="grid-value-filter-tree" checkable checkStrictly selectable={false} blockNode
      checkedKeys={checked} treeData={visible} height={280} expandedKeys={expandedKeys} onExpand={keys => setExpanded(keys.map(String))} onCheck={(_keys, event) => onModelChange(toggleValueFilter(model, event.node.values, event.checked))}
      titleRender={node => <span className="grid-value-filter-candidate"><span className="grid-value-filter-label">{node.label}</span><span className="grid-value-filter-count">{node.count}</span>
        <Button type="text" size="small" className="grid-value-filter-only" aria-label={`仅筛选此项：${node.label}`} onPointerDown={e => e.stopPropagation()} onClick={e => { e.stopPropagation(); onModelChange({ values: [...node.values] }); close.current?.(); }}>仅此项</Button></span>} /> : <p className="state">没有符合搜索的候选。</p>}
    <div className="grid-value-filter-actions"><Button onClick={() => { onModelChange(null); close.current?.(); }}>清除筛选</Button></div>
  </div>;
}

// Compose native column definitions; AG owns the per-grid model, popup and row filtering.
export function valueFilterColumn<T>(column: ColDef<T>, options: ValueFilterOptions<T>): ColDef<T> {
  return { ...column, cellDataType: false, sortable: column.sortable ?? true, suppressHeaderFilterButton: false,
    comparator: column.comparator ?? ((_a, _b, a, b) => compareFilterValues(a.data ? options.value(a.data) : null, b.data ? options.value(b.data) : null, options.kind)),
    filter: { component: ValueFilter, doesFilterPass: ({ data, model }: DoesFilterPassParams<T, unknown, ValueFilterModel>) => (options.keepVisible?.(data) ?? false) || valueFilterPasses(model, options.value(data), options.kind) },
    filterParams: { ...column.filterParams, valueFilter: options, buttons: [] } };
}
