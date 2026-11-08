import React, { useEffect, useState } from "react";
import {
  fetchCandles,
  fetchOptionChain,
  fetchQualityReport,
  fetchTicks,
  fetchUnderlyings,
} from "./api";
import { CandlestickChart } from "./components/CandlestickChart";
import { OptionChainTable } from "./components/OptionChainTable";
import { QualityDashboard } from "./components/QualityDashboard";
import {
  MatchedTick,
  OhlcvCandle,
  OptionChainResponse,
  QualityReport,
  UnderlyingAsset,
} from "./types";

const TIMEFRAMES: Array<"1m" | "5m" | "15m" | "1h" | "1d"> = ["1m", "5m", "15m", "1h", "1d"];

export const App: React.FC = () => {
  const [underlyings, setUnderlyings] = useState<UnderlyingAsset[]>([]);
  const [selectedUa, setSelectedUa] = useState<string>("46348559193224090");
  const [selectedDate, setSelectedDate] = useState<number | undefined>(undefined);
  const [timeframe, setTimeframe] = useState<"1m" | "5m" | "15m" | "1h" | "1d">("1m");
  const [includeExpired, setIncludeExpired] = useState<boolean>(true);

  const [chainData, setChainData] = useState<OptionChainResponse | null>(null);
  const [selectedOption, setSelectedOption] = useState<{
    insCode: string;
    symbol: string;
  }>({
    insCode: "90000000000000001",
    symbol: "ضفلا1100",
  });

  const [uaCandles, setUaCandles] = useState<OhlcvCandle[]>([]);
  const [optionCandles, setOptionCandles] = useState<OhlcvCandle[]>([]);
  const [matchedTicks, setMatchedTicks] = useState<MatchedTick[]>([]);
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null);

  useEffect(() => {
    fetchUnderlyings().then(setUnderlyings).catch(console.error);
    fetchQualityReport().then(setQualityReport).catch(console.error);
  }, []);

  useEffect(() => {
    fetchOptionChain(selectedUa, selectedDate, includeExpired)
      .then((res) => {
        setChainData(res);
        const firstCall = res.chain.find((r) => r.call_ins_code)?.call_ins_code;
        const firstSym = res.chain.find((r) => r.call_symbol)?.call_symbol;
        if (firstCall && firstSym) {
          setSelectedOption({ insCode: firstCall, symbol: firstSym });
        }
      })
      .catch(console.error);
  }, [selectedUa, selectedDate, includeExpired]);

  useEffect(() => {
    fetchCandles(selectedUa, timeframe, selectedDate).then(setUaCandles).catch(console.error);
  }, [selectedUa, timeframe, selectedDate]);

  useEffect(() => {
    if (!selectedOption.insCode) return;
    fetchCandles(selectedOption.insCode, timeframe, selectedDate)
      .then(setOptionCandles)
      .catch(console.error);
    fetchTicks(selectedOption.insCode, selectedDate, 200)
      .then(setMatchedTicks)
      .catch(console.error);
  }, [selectedOption, timeframe, selectedDate]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-6 space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">
            سکوی تحلیل داده‌های تیک بازار اختیار معامله بورس تهران (TSETMC)
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            پوشش ۲۵ دارایی پایه • قراردادهای فعال و منقضی‌شده از ۱۴۰۲ • تطبیق دقیق تیک و روزانه • ASOF JOIN
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          <label className="flex items-center gap-1.5">
            <span className="text-slate-400">دارایی پایه:</span>
            <select
              value={selectedUa}
              onChange={(e) => {
                setSelectedUa(e.target.value);
                setSelectedDate(undefined);
              }}
              className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100"
            >
              {underlyings.map((u) => (
                <option key={u.ins_code} value={u.ins_code}>
                  {u.symbol} — {u.full_name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-1.5">
            <span className="text-slate-400">تاریخ معاملاتی:</span>
            <select
              value={selectedDate || ""}
              onChange={(e) =>
                setSelectedDate(e.target.value ? Number(e.target.value) : undefined)
              }
              className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-100 font-mono"
            >
              <option value="">آخرین روز معاملاتی</option>
              {(chainData?.available_dates || []).map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-center bg-slate-900 border border-slate-700 rounded-lg p-0.5">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => setTimeframe(tf)}
                className={`px-2.5 py-1 rounded-md font-mono transition ${
                  timeframe === tf ? "bg-sky-600 text-white" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={includeExpired}
              onChange={(e) => setIncludeExpired(e.target.checked)}
              className="rounded border-slate-700"
            />
            <span className="text-slate-300">نمایش قراردادهای منقضی‌شده</span>
          </label>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CandlestickChart
          title={`نمودار دارایی پایه: ${chainData?.symbol || ""}`}
          subtitle={`آخرین قیمت پایه: ${(chainData?.underlying_price || 0).toLocaleString()} ریال • بازه زمانی ${timeframe}`}
          candles={uaCandles}
        />
        <CandlestickChart
          title={`نمودار قرارداد اختیار: ${selectedOption.symbol}`}
          subtitle={`کد ابزار: ${selectedOption.insCode} • خط آبی: قیمت مرجع پرشده (close_ffill)`}
          candles={optionCandles}
        />
      </div>

      {chainData && (
        <OptionChainTable
          chain={chainData.chain}
          selectedOptionInsCode={selectedOption.insCode}
          onSelectOption={(insCode, symbol) => setSelectedOption({ insCode, symbol })}
        />
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow overflow-x-auto">
        <h3 className="text-sm font-semibold text-slate-100 mb-3">
          جریان تیک‌های قرارداد ({selectedOption.symbol}) همگام‌سازی‌شده با قیمت لحظه‌ای دارایی پایه (`ASOF JOIN`)
        </h3>
        <table className="w-full text-xs text-center border-collapse">
          <thead>
            <tr className="bg-slate-950 text-slate-400 border-b border-slate-800">
              <th className="py-2 px-2">ردیف (nTran)</th>
              <th className="py-2 px-2">زمان تهران (+03:30)</th>
              <th className="py-2 px-2">زمان UTC</th>
              <th className="py-2 px-2">قیمت اختیار</th>
              <th className="py-2 px-2">حجم</th>
              <th className="py-2 px-2 text-sky-400">قیمت همزمان دارایی پایه (ASOF)</th>
              <th className="py-2 px-2">زمان معامله پایه</th>
              <th className="py-2 px-2">وضعیت (Moneyness)</th>
            </tr>
          </thead>
          <tbody>
            {matchedTicks.map((t) => (
              <tr
                key={`${t.d_even}_${t.n_tran}`}
                className="border-b border-slate-800/60 hover:bg-slate-800/30 font-mono"
              >
                <td className="py-1.5 px-2">{t.n_tran}</td>
                <td className="py-1.5 px-2 text-slate-300">{t.ts_tehran}</td>
                <td className="py-1.5 px-2 text-slate-400">{t.ts_utc}</td>
                <td className="py-1.5 px-2 text-emerald-400 font-bold">
                  {t.price.toLocaleString()}
                </td>
                <td className="py-1.5 px-2">{t.volume.toLocaleString()}</td>
                <td className="py-1.5 px-2 text-sky-300 font-bold">
                  {t.underlying_price !== null ? t.underlying_price.toLocaleString() : "—"}
                </td>
                <td className="py-1.5 px-2 text-slate-400">{t.underlying_ts_utc || "—"}</td>
                <td className="py-1.5 px-2">{t.moneyness_status || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <QualityDashboard report={qualityReport} />
    </div>
  );
};

export default App;
