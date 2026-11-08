import React from "react";
import { OptionChainRow } from "../types";

interface OptionChainTableProps {
  chain: OptionChainRow[];
  selectedOptionInsCode: string | null;
  onSelectOption: (insCode: string, symbol: string) => void;
}

const moneynessBadge = (status: "ITM" | "ATM" | "OTM" | null) => {
  if (!status) return null;
  const styles: Record<string, string> = {
    ITM: "bg-emerald-900/70 text-emerald-300 border-emerald-700",
    ATM: "bg-amber-900/70 text-amber-300 border-amber-700",
    OTM: "bg-slate-800 text-slate-400 border-slate-700",
  };
  return (
    <span className={`px-1.5 py-0.5 text-[11px] font-mono rounded border ${styles[status]}`}>
      {status}
    </span>
  );
};

export const OptionChainTable: React.FC<OptionChainTableProps> = ({
  chain,
  selectedOptionInsCode,
  onSelectOption,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow overflow-x-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-100">
          زنجیره قراردادهای اختیار معامله (Option Chain — Call / Strike / Put)
        </h3>
        <span className="text-xs text-slate-400">
          برای مشاهده نمودار کندل و جریان تیک همگام (`ASOF JOIN`) روی نماد کلیک کنید
        </span>
      </div>

      <table className="w-full text-xs text-center border-collapse">
        <thead>
          <tr className="bg-slate-950 text-slate-400 border-b border-slate-800">
            <th className="py-2 px-2 text-emerald-400">نماد خرید (Call)</th>
            <th className="py-2 px-2">وضعیت</th>
            <th className="py-2 px-2">آخرین قیمت</th>
            <th className="py-2 px-2">حجم</th>
            <th className="py-2 px-2">تقاضا / عرضه</th>
            <th className="py-2 px-3 bg-slate-800/80 text-sky-300 font-bold">
              قیمت اعمال (Strike)
            </th>
            <th className="py-2 px-2 bg-slate-800/50 text-slate-300">سررسید (DTE)</th>
            <th className="py-2 px-2 text-rose-400">نماد فروش (Put)</th>
            <th className="py-2 px-2">وضعیت</th>
            <th className="py-2 px-2">آخرین قیمت</th>
            <th className="py-2 px-2">حجم</th>
            <th className="py-2 px-2">تقاضا / عرضه</th>
          </tr>
        </thead>
        <tbody>
          {chain.map((row) => {
            const isCallSelected =
              row.call_ins_code !== null && row.call_ins_code === selectedOptionInsCode;
            const isPutSelected =
              row.put_ins_code !== null && row.put_ins_code === selectedOptionInsCode;

            return (
              <tr
                key={`${row.end_date}_${row.strike_price}`}
                className="border-b border-slate-800/70 hover:bg-slate-800/40 transition-colors"
              >
                <td className="py-2 px-2">
                  {row.call_ins_code && row.call_symbol ? (
                    <button
                      type="button"
                      onClick={() => onSelectOption(row.call_ins_code!, row.call_symbol!)}
                      className={`px-2 py-1 rounded font-semibold transition ${
                        isCallSelected
                          ? "bg-emerald-600 text-white"
                          : "bg-emerald-950/60 text-emerald-300 hover:bg-emerald-900"
                      }`}
                    >
                      {row.call_symbol}
                    </button>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="py-2 px-2">{moneynessBadge(row.call_moneyness)}</td>
                <td className="py-2 px-2 font-mono">{row.call_last.toLocaleString()}</td>
                <td className="py-2 px-2 font-mono">{row.call_volume.toLocaleString()}</td>
                <td className="py-2 px-2 font-mono text-slate-400">
                  {row.call_bid} / {row.call_ask}
                </td>

                <td className="py-2 px-3 bg-slate-800/60 font-mono font-bold text-sky-300">
                  {row.strike_price.toLocaleString()}
                </td>
                <td className="py-2 px-2 bg-slate-800/30 font-mono text-slate-300">
                  {row.end_date} <span className="text-slate-400">({row.dte}d)</span>
                </td>

                <td className="py-2 px-2">
                  {row.put_ins_code && row.put_symbol ? (
                    <button
                      type="button"
                      onClick={() => onSelectOption(row.put_ins_code!, row.put_symbol!)}
                      className={`px-2 py-1 rounded font-semibold transition ${
                        isPutSelected
                          ? "bg-rose-600 text-white"
                          : "bg-rose-950/60 text-rose-300 hover:bg-rose-900"
                      }`}
                    >
                      {row.put_symbol}
                    </button>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="py-2 px-2">{moneynessBadge(row.put_moneyness)}</td>
                <td className="py-2 px-2 font-mono">{row.put_last.toLocaleString()}</td>
                <td className="py-2 px-2 font-mono">{row.put_volume.toLocaleString()}</td>
                <td className="py-2 px-2 font-mono text-slate-400">
                  {row.put_bid} / {row.put_ask}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
