import Button from 'antd/es/button';
import { Component, useState } from 'react';
import type { ReactNode } from 'react';
import { useHistoryProtection } from './history';

function PageFailure({ title }: { title: string }) {
  const protection = useHistoryProtection(), [reason, setReason] = useState('');
  function reload() {
    const blocked = protection();
    if (blocked) { setReason(blocked); return; }
    window.location.reload();
  }
  return <div className="notice" role="alert"><span>{title}未能加载，请检查连接后重新加载页面。{reason && <span> {reason}</span>}</span><Button onClick={reload}>重新加载页面</Button></div>;
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
