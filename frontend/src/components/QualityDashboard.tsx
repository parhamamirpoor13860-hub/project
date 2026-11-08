import React from "react";
import { QualityReport } from "../types";

interface QualityDashboardProps {
  report: QualityReport | null;
}

export const QualityDashboard: React.FC<QualityDashboardProps> = ({ report }) => {
  if (!report) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-xs text-slate-400">
        در حال بارگذاری گزارش کنترل کیفیت و تطبیق داده‌ها...
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">
            گزارش اعتبارسنجی و تطبیق داده‌های تیک با آمار رسمی روزانه (Stage 4 Reconciliation)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            تطبیق تعداد معاملات معتبر (`canceled == 0`) با `zTotTran` و حجم معاملات با `qTotTran5J`
          </p>
        </div>
        <div
          className={`px-3 py-1 rounded-full text-xs font-bold ${
            report.meets_98_pct_target
              ? "bg-emerald-900/80 text-emerald-300 border border-emerald-700"
              : "bg-rose-900/80 text-rose-300 border border-rose-700"
          }`}
        >
          نرخ تطبیق: {report.match_rate_pct}% (هدف پذیرش ≥ 98%)
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-center">
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
          <div className="text-xs text-slate-400">کل روزهای معاملاتی</div>
          <div className="text-lg font-bold font-mono text-slate-100 mt-1">
            {report.total_traded_days}
          </div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
          <div className="text-xs text-slate-400">روزهای منطبق (MATCH)</div>
          <div className="text-lg font-bold font-mono text-emerald-400 mt-1">
            {report.matched_days}
          </div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
          <div className="text-xs text-slate-400">عدم تطبیق / کسری</div>
          <div className="text-lg font-bold font-mono text-amber-400 mt-1">
            {report.mismatched_days + report.missing_days}
          </div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
          <div className="text-xs text-slate-400">معاملات ابطال‌شده (`canceled=1`)</div>
          <div className="text-lg font-bold font-mono text-sky-400 mt-1">
            {report.canceled_trades_count}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs text-center border-collapse">
          <thead>
            <tr className="bg-slate-950 text-slate-400 border-b border-slate-800">
              <th className="py-2 px-2">نماد</th>
              <th className="py-2 px-2">کد ابزار (insCode)</th>
              <th className="py-2 px-2">تاریخ (dEven)</th>
              <th className="py-2 px-2">تعداد روزانه (zTotTran)</th>
              <th className="py-2 px-2">تیک معتبر</th>
              <th className="py-2 px-2">تیک باطل‌شده</th>
              <th className="py-2 px-2">حجم روزانه (qTotTran5J)</th>
              <th className="py-2 px-2">حجم تیک معتبر</th>
              <th className="py-2 px-2">وضعیت</th>
            </tr>
          </thead>
          <tbody>
            {report.rows.map((r) => (
              <tr
                key={`${r.ins_code}_${r.d_even}`}
                className="border-b border-slate-800/60 hover:bg-slate-800/30"
              >
                <td className="py-1.5 px-2 font-semibold text-slate-200">{r.symbol}</td>
                <td className="py-1.5 px-2 font-mono text-slate-400">{r.ins_code}</td>
                <td className="py-1.5 px-2 font-mono">{r.d_even}</td>
                <td className="py-1.5 px-2 font-mono">{r.daily_trade_count}</td>
                <td className="py-1.5 px-2 font-mono text-emerald-400">{r.tick_valid_count}</td>
                <td className="py-1.5 px-2 font-mono text-amber-400">{r.tick_canceled_count}</td>
                <td className="py-1.5 px-2 font-mono">{r.daily_volume.toLocaleString()}</td>
                <td className="py-1.5 px-2 font-mono">{r.tick_valid_volume.toLocaleString()}</td>
                <td className="py-1.5 px-2">
                  <span
                    className={`px-2 py-0.5 rounded font-mono text-[11px] ${
                      r.status === "MATCH"
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                        : "bg-rose-950 text-rose-300 border border-rose-700"
                    }`}
                  >
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
