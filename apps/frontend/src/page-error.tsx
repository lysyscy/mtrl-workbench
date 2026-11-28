import Button from 'antd/es/button';
import { Component, useState } from 'react';
import type { ReactNode } from 'react';
import { useReloadProtection } from './history';

export function WorkspaceReloadButton({ children }: { children: ReactNode }) {
  const protection = useReloadProtection(), [reason, setReason] = useState('');
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

export class PageErrorBoundary extends Component<{ active: boolean; title: string; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (!this.state.failed) return this.props.children;
    return <div className="page-view" data-page-layout="flow" hidden={!this.props.active}>
      <section className="wb-surface" data-route-error><PageFailure title={this.props.title} /></section>
    </div>;
  }
}
