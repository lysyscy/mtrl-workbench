import test from 'node:test';
import assert from 'node:assert/strict';
import { QueryClient, QueryObserver } from '@tanstack/react-query';
import { noticeTodosKey, resetNoticeTodos } from '../../src/notice-todos.ts';

test('a notice write discards a delayed home count and reads again only when home is active', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const reads = [];
  const options = {
    queryKey: noticeTodosKey,
    queryFn: ({ signal }) => new Promise(resolve => reads.push({ signal, resolve })),
  };
  const home = new QueryObserver(client, options);
  const unsubscribe = home.subscribe(() => {});
  try {
    assert.equal(reads.length, 1);
    const refresh = resetNoticeTodos(client);
    assert.equal(reads[0].signal.aborted, true);
    assert.equal(reads.length, 2);
    reads[1].resolve({ jc: 0 });
    await refresh;
    reads[0].resolve({ jc: 1 });
    await Promise.resolve();
    assert.deepEqual(client.getQueryData(noticeTodosKey), { jc: 0 });

    home.setOptions({ ...options, enabled: false });
    await resetNoticeTodos(client);
    assert.equal(reads.length, 2);
    assert.equal(client.getQueryData(noticeTodosKey), undefined);
    home.setOptions(options);
    assert.equal(reads.length, 3);
    reads[2].resolve({ jc: 2 });
    await home.refetch();
    assert.deepEqual(client.getQueryData(noticeTodosKey), { jc: 2 });
  } finally {
    unsubscribe();
    client.clear();
  }
});
