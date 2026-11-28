import type { QueryClient } from '@tanstack/react-query';

export const noticeTodosKey = ['notices', 'home-todos'] as const;

export function resetNoticeTodos(client: QueryClient) {
  return client.resetQueries({ queryKey: noticeTodosKey, exact: true });
}
