import { cents, decimal } from './api';

export type OverageSide = 'supplier' | 'trade';

export interface SubtableOverage {
  /** 已保存累计超过 110% 阈值（严格 >110%，恰好 110% 不算超） */
  over: boolean;
  /** 合同额缺失/非正/不可解析：此时 over 恒为 false */
  missingContract: boolean;
  /** 已保存累计金额，decimal() 形式（2 位小数文本，无千分位、无货币符号） */
  saved: string;
  /** 合同额 decimal() 形式；缺失为 null */
  contract: string | null;
  /** 已保存累计 / 合同额 * 100，保留 1 位小数（四舍五入到 0.1）；不可算时 null。例：'112.5' */
  ratio: string | null;
  /** 相对合同额超出的百分比，112% 占比对应超出 12%，保留 1 位小数。 */
  excessRatio: string | null;
  projectedExcessRatio: string | null;
  /** 含本次未保存合法输入的累计，decimal() 形式；无合法输入时等于 saved */
  projected: string;
  /** 加上本次输入后是否将超过阈值；仅当本次输入是合法正金额且超阈值才 true */
  projectedOver: boolean;
}

/** 整数四舍五入除法（半数远离零），只走 bigint，不经过浮点。 */
function roundHalfUp(numerator: bigint, denominator: bigint): bigint {
  const negative = (numerator < 0n) !== (denominator < 0n);
  const n = numerator < 0n ? -numerator : numerator;
  const d = denominator < 0n ? -denominator : denominator;
  const rounded = (n * 2n + d) / (d * 2n);
  return negative ? -rounded : rounded;
}

/** 阈值比较的唯一出口：累计 * 100 > 合同 * 110，整数 cents，避免浮点百分比误差。 */
const exceedsThreshold = (totalCents: bigint, contractCents: bigint) => totalCents * 100n > contractCents * 110n;

/** cents() 解析失败或非正都视为"无合同额"：金额不可判断时宁可不上报超额。 */
function contractCentsOf(value: string | null | undefined): bigint | null {
  if (value === null || value === undefined) return null;
  let parsed: bigint;
  try { parsed = cents(value); } catch { return null; }
  return parsed > 0n ? parsed : null;
}

/** 输入框里的半截数字（'12.'、'1.234'、'abc'、''）属于常态，按"无输入"处理而不是抛错。 */
function pendingCentsOf(value: string | null | undefined): bigint | null {
  if (value === null || value === undefined) return null;
  let parsed: bigint;
  try { parsed = cents(value); } catch { return null; }
  return parsed > 0n ? parsed : null;
}

export function subtableOverage(input: {
  side: OverageSide;
  savedTotal: string;
  contractAmount: string | null | undefined;
  pendingAmount?: string | null;
}): SubtableOverage {
  // side 只影响调用方文案，数值判定两侧共用同一套 cents 规则。
  const savedCents = cents(input.savedTotal);
  const saved = decimal(savedCents);
  const contractCents = contractCentsOf(input.contractAmount);
  const pendingCents = pendingCentsOf(input.pendingAmount);
  const projectedCents = pendingCents === null ? savedCents : savedCents + pendingCents;

  if (contractCents === null) {
    return {
      over: false,
      missingContract: true,
      saved,
      contract: null,
      ratio: null,
      excessRatio: null,
      projectedExcessRatio: null,
      projected: decimal(projectedCents),
      projectedOver: false,
    };
  }

  // 0.1% 精度即 1/1000：ratioTenths = round(saved * 1000 / contract)，全程整数。
  const ratioTenths = roundHalfUp(savedCents * 1000n, contractCents);
  const ratioAbs = ratioTenths < 0n ? -ratioTenths : ratioTenths;
  const excess = (total: bigint) => {
    const value = roundHalfUp((total - contractCents) * 1000n, contractCents);
    const absolute = value < 0n ? -value : value;
    return `${value < 0n ? '-' : ''}${absolute / 10n}.${absolute % 10n}`;
  };
  return {
    over: exceedsThreshold(savedCents, contractCents),
    missingContract: false,
    saved,
    contract: decimal(contractCents),
    ratio: `${ratioTenths < 0n ? '-' : ''}${ratioAbs / 10n}.${ratioAbs % 10n}`,
    excessRatio: excess(savedCents),
    projectedExcessRatio: excess(projectedCents),
    projected: decimal(projectedCents),
    projectedOver: pendingCents !== null && projectedCents > savedCents && exceedsThreshold(projectedCents, contractCents),
  };
}
