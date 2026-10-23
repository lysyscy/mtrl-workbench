import ConfigProvider from 'antd/es/config-provider';
import theme from 'antd/es/theme';
import zhCN from 'antd/locale/zh_CN';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import './ui.css';

function tokens() {
  const css = getComputedStyle(document.documentElement);
  const read = (name: string) => css.getPropertyValue(name).trim();
  const scale = Number(read('--fscale')) || 1;
  return { fontFamily: read('--fs') || 'MiSans, sans-serif', fontSize: 14 * scale,
    controlHeight: 32 * scale, controlHeightSM: 28 * scale, borderRadius: 5,
    colorPrimary: read('--pri') || '#176baf', colorText: read('--tx') || '#202020',
    colorTextSecondary: read('--tx2') || '#555555', colorBgContainer: read('--sf') || '#ffffff',
    colorBgElevated: read('--sf') || '#ffffff', colorBorder: read('--bd3') || '#bfbfbf',
    colorBgLayout: read('--bg') || '#f5f5f5', colorFillSecondary: read('--sf2') || '#f3f3f3',
    colorSuccess: '#238636', colorWarning: '#ad6800', colorError: '#c42b34', motion: false };
}

export function UiProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(tokens);
  useEffect(() => {
    const update = () => setToken(tokens());
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class'] });
    const stylesheet = document.querySelector('#user-theme');
    stylesheet?.addEventListener('load', update); update();
    return () => { observer.disconnect(); stylesheet?.removeEventListener('load', update); };
  }, []);
  return <ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }} componentSize="small" theme={{ algorithm: theme.compactAlgorithm, token }}>{children}</ConfigProvider>;
}
