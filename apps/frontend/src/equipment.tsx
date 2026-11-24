import { useCallback, useContext, useState } from 'react';
import { PageActivity } from './page-activity';
import { MotionAccess } from './workspace-motion';
import Tabs from 'antd/es/tabs';
import type { Identity } from './api';
import { EquipmentAccess } from './equipment-ui';
import { Distribution } from './equipment-distribution';
import { Rental } from './equipment-rental';
import { Inventory } from './equipment-inventory';
import type { RentalTarget } from './equipment-navigation';

type Jump = { tab: 'rental'; target: RentalTarget } | { tab: 'distribution'; ids: readonly number[] };

export function EquipmentPage({ me, blocked }: { me: Identity | null; blocked: boolean }) {
  const visible = useContext(MotionAccess);
  const [tab, setTab] = useState('distribution');
  const [jump, setJump] = useState<Jump | null>(null);
  const scale = Number(me?.ui_scale_css) || 1;
  const goToRental = useCallback((target: RentalTarget) => {
    setJump({ tab: 'rental', target });
    setTab('rental');
  }, []);
  const goToDistribution = useCallback((ids: readonly number[]) => {
    setJump({ tab: 'distribution', ids: [...ids] });
    setTab('distribution');
  }, []);
  const sections = [
    { key: 'distribution', label: '设备分布', page: <Distribution scale={scale}
      targetIds={jump?.tab === 'distribution' ? jump.ids : null} goToRental={goToRental} /> },
    { key: 'rental', label: '租赁表', page: <Rental scale={scale}
      target={jump?.tab === 'rental' ? jump.target : null} goToDistribution={goToDistribution} /> },
    { key: 'inventory', label: '盘点表', page: <Inventory scale={scale} goToDistribution={goToDistribution} /> },
  ];
  return (
    <section className="equipment-page equipment-page-bounded" aria-label="设备台账">
      <Tabs
        className="equipment-top-tabs"
        classNames={{ body: 'equipment-tabs-body', content: 'equipment-tab-panel' }}
        activeKey={tab}
        onChange={key => { setJump(null); setTab(key); }}
        items={sections.map(({ key, label, page }) => ({
          key,
          label,
          children: (
            <PageActivity.Provider value={!blocked && key === tab}>
              <MotionAccess.Provider value={visible && !blocked && key === tab}>
                <EquipmentAccess.Provider
                  value={{ enabled: !blocked && key === tab, writable: !!me && !blocked && key === tab }}
                >
                  {page}
                </EquipmentAccess.Provider>
              </MotionAccess.Provider>
            </PageActivity.Provider>
          ),
        }))}
      />
    </section>
  );
}
