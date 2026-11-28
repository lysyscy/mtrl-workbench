export interface LayoutInput<T> {
  data: T | undefined;
  node: { rowPinned: 'top' | 'bottom' | null | undefined; rowIndex?: number | null } | null;
}
const layoutReader = Symbol('grid layout reader');
export function layoutCallback<T, Result = unknown>(read: (input: LayoutInput<T>) => Result): (input: LayoutInput<T>) => Result {
  return Object.assign(read, { [layoutReader]: read });
}
export function readLayout<T>(callback: unknown, input: LayoutInput<T>): unknown {
  if (typeof callback !== 'function' || !(layoutReader in callback) || typeof callback[layoutReader] !== 'function') {
    throw new Error('Use layoutCallback for a measured grid callback.');
  }
  return callback[layoutReader](input);
}

