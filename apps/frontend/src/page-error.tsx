import Button from 'antd/es/button';
import { Component, useState } from 'react';
import type { ReactNode } from 'react';
import { useHistoryProtection } from './history';

// Every explicit document reload inside the account tree uses the same live
// protection. A blocked retry leaves the navigation and owning input intact.
export function WorkspaceReloadButton({ children }: { children: ReactNode }) {
  const protection = useHistoryProtection(), [reason, setReason] = useState('');
  function reload() {
    const blocked = protection();
    if (blocked) { setReason(blocked); return; }
    window.location.reload();
  }
  return <><Button onClick={reload}>{children}</Button>{reason && <span role="status">{reason}</span>}</>;
}

function PageFailure({ title }: { title: string }) {
  return <div className="notice" role="alert"><span>{title}未能加载，请检查连接后重新加载页面。</span><WorkspaceReloadButton>重新加载页面</WorkspaceReloadButton></div>;
}

// React.lazy caches rejected imports. Keep the shell and other page drafts alive;
// an explicit reload retries the module only after the existing write/draft guards allow it.
export class PageErrorBoundary extends Component<{ active: boolean; title: string; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <section hidden={!this.props.active} data-route-error><PageFailure title={this.props.title} /></section> : this.props.children;
  }
}
