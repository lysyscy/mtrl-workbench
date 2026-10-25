import { Provider as MotionProvider } from '@rc-component/motion';
import App from 'antd/es/app';
import ConfigProvider from 'antd/es/config-provider';
import theme from 'antd/es/theme';
import zhCN from 'antd/locale/zh_CN';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import './ui.css';

function appearance() {
  const css = getComputedStyle(document.documentElement);
  const read = (name: string) => css.getPropertyValue(name).trim();
  const scale = Number(read('--fscale')) || 1;
  const radius = Number.parseFloat(read('--radius-input')) || 10;
  return { dark: read('--ui-scheme') === 'dark', token: {
    fontFamily: read('--fs') || 'MiSans, sans-serif', fontSize: (Number(read('--font-ui-size')) || 13.5) * scale,
    controlHeight: 32 * scale, controlHeightSM: 32 * scale,
    borderRadius: radius, borderRadiusSM: radius, borderRadiusLG: Number.parseFloat(read('--radius-card')) || 16,
    colorPrimary: read('--pri'), colorTextLightSolid: read('--on'), colorPrimaryHover: read('--pri-d'), colorText: read('--tx'),
    colorTextSecondary: read('--tx2'), colorTextPlaceholder: read('--tx2'),
    colorBgContainer: read('--sf'), colorBgElevated: read('--sf'), colorBorder: read('--bd3'),
    colorBgLayout: read('--bg'), colorFillSecondary: read('--sf2'),
    colorSuccess: read('--ok-d'), colorWarning: read('--wn-d'), colorError: read('--dg-d'), colorInfo: read('--bl-d'),
    boxShadow: read('--shadow-pop'), boxShadowSecondary: read('--shadow-md'),
    motionDurationFast: read('--motion-fast') || '130ms', motionDurationMid: read('--motion-fast') || '130ms', motionDurationSlow: read('--motion-fast') || '130ms',
  } };
}

export function UiProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState(appearance);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    const update = () => setValue(appearance());
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class'] });
    const stylesheet = document.querySelector('#user-theme');
    stylesheet?.addEventListener('load', update); update();
    return () => { observer.disconnect(); stylesheet?.removeEventListener('load', update); };
  }, []);
  // Keep the provider tree stable when the OS motion preference changes mid-edit.
  return <MotionProvider motion={!reducedMotion}><ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }} componentSize="small" theme={{
    algorithm: value.dark ? [theme.darkAlgorithm, theme.compactAlgorithm] : theme.compactAlgorithm,
    token: value.token, components: { Button: { borderRadius: 999, borderRadiusSM: 999 }, Tag: { borderRadiusSM: 999 }, Checkbox: { borderRadiusSM: 4 } },
  }}><App component={false}>{children}</App></ConfigProvider></MotionProvider>;
}
