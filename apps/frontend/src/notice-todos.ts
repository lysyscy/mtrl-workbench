import type { QueryClient } from '@tanstack/react-query';

export const noticeTodosKey = ['notices', 'home-todos'] as const;

// A write may finish while the first summary GET is still pending. Reset
// cancels that read and drops prior counts. Only an active home reads again.
export function resetNoticeTodos(client: QueryClient) {
  return client.resetQueries({ queryKey: noticeTodosKey, exact: true });
}
