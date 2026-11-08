import React, { useEffect, useRef } from "react";
import { createChart, ColorType, UTCTimestamp } from "lightweight-charts";
import { OhlcvCandle } from "../types";

interface CandlestickChartProps {
  title: string;
  subtitle?: string;
  candles: OhlcvCandle[];
  height?: number;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  title,
  subtitle,
  candles,
  height = 320,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      width: el.clientWidth || 640,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#0f172a" },
        textColor: "#cbd5e1",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#334155",
      },
      rightPriceScale: {
        borderColor: "#334155",
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    const ffillSeries = chart.addLineSeries({
      color: "#38bdf8",
      lineWidth: 1,
      title: "close_ffill",
    });

    const volumeSeries = chart.addHistogramSeries({
      color: "#6366f1",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
    });

    const sorted = [...candles].sort((a, b) => a.bucket_epoch - b.bucket_epoch);

    candleSeries.setData(
      sorted.map((c) => ({
        time: c.bucket_epoch as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    ffillSeries.setData(
      sorted.map((c) => ({
        time: c.bucket_epoch as UTCTimestamp,
        value: c.close_ffill,
      }))
    );

    volumeSeries.setData(
      sorted.map((c) => ({
        time: c.bucket_epoch as UTCTimestamp,
        value: c.volume,
        color: c.is_sparse ? "#334155" : c.close >= c.open ? "#05966988" : "#dc262688",
      }))
    );

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [candles, height]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
        <div className="text-xs text-slate-400">
          تعداد کندل: <span className="text-sky-400 font-mono">{candles.length}</span> (امید به پرشدن شکاف:{" "}
          <span className="text-amber-400 font-mono">
            {candles.filter((c) => c.is_sparse === 1).length}
          </span>
          )
        </div>
      </div>
      <div ref={containerRef} className="w-full overflow-hidden rounded-lg" />
    </div>
  );
};
