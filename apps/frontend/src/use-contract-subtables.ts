import { useLayoutEffect, useRef, useSyncExternalStore } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import App from 'antd/es/app';
import { requestJson } from './api';
import { contractWrite, readContracts } from './contracts-api';
import { loadSubtables, readSubtableOperation, writeSubtable } from './contract-subtables-api';
import { ContractSubtableWorkspace } from './contract-subtable-workspace';

export function useContractSubtables(accountId: number | undefined, enabled: boolean) {
  const client = useQueryClient(), { message } = App.useApp();
  const active = useRef(enabled); active.current = enabled;
  const ref = useRef<ContractSubtableWorkspace | null>(null);
  if (!ref.current) ref.current = new ContractSubtableWorkspace(accountId, {
    allowed: () => active.current,
    write: (id, operation) => writeSubtable(id, operation.kind, operation.action === 'del' ? null : {
      date: operation.date, amount: operation.amount, initialDate: operation.date,
    }, operation.rowId ?? undefined, operation.requestId),
    lookup: readSubtableOperation,
    refresh: async id => {
      await client.invalidateQueries({ refetchType: 'none' });
      void client.invalidateQueries({ predicate: query => query.queryKey[0] === 'history' && query.isActive() });
      await Promise.all([
        client.cancelQueries({ queryKey: ['contract-subtables', id], exact: true }),
        client.cancelQueries({ queryKey: ['contracts'], exact: true }),
      ]);
      await Promise.all([
        client.fetchQuery({ queryKey: ['contract-subtables', id], staleTime: 0, queryFn: ({ signal }) => loadSubtables(id, signal) }),
        client.fetchQuery({ queryKey: ['contracts'], staleTime: 0, queryFn: async ({ signal }) => readContracts(await requestJson('/api/m11/list', { signal })) }),
      ]);
    },
    reference: async (id, noticeId) => { await contractWrite('/api/m11/link', { notice_id: noticeId, contract_id: id }); },
    announce: content => { void message.success({ key: 'contract-subtable-success', content, duration: 3 }); },
  });
  const workspace = ref.current;
  useSyncExternalStore(workspace.subscribe, workspace.getSnapshot);
  useLayoutEffect(() => { workspace.mount(); return workspace.dispose; }, [workspace]);
  return workspace;
}
