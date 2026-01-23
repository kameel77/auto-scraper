"use client";

import { startScrape } from "@/lib/api";
import { useState } from "react";

export function ScrapeButton() {
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<{ status: string; current?: number; total?: number } | null>(null);
  const [marketplace, setMarketplace] = useState<string>("autopunkt");
  const [limit, setLimit] = useState<number | "">("");

  const handleScrape = async () => {
    setLoading(true);
    setProgress({ status: `Uruchamianie scrapera dla ${marketplace}...` });

    const limitParam = limit === "" ? "all" : limit;

    try {
      const eventSource = new EventSource(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/scrape/progress?marketplace=${marketplace}&limit=${limitParam}`);

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.status === "progress" || data.status === "collecting" || data.status === "scraping") {
          setProgress({ status: data.message, current: data.current, total: data.total });
        } else if (data.status === "complete") {
          setProgress({ status: `Zakończono! Zebrał ${data.collected} ofert`, current: data.collected, total: data.collected });
          eventSource.close();
          setTimeout(() => {
            setLoading(false);
            setProgress(null);
            window.location.reload();
          }, 2000);
        } else if (data.status === "error") {
          setProgress({ status: `Błąd: ${data.message}` });
          eventSource.close();
          setLoading(false);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setLoading(false);
        setProgress({ status: "Błąd połączenia z serwerem" });
      };

      await startScrape(marketplace, limit === "" ? 0 : limit);
    } catch (error) {
      console.error("Scrape failed:", error);
      setLoading(false);
      setProgress({ status: "Nie udało się uruchomić scrapera" });
    }
  };

  const handleReset = async () => {
    if (!confirm("Czy na pewno chcesz wyczyścić bazę danych?")) return;

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/admin/reset-db`, {
        method: "POST",
      });
      if (res.ok) {
        alert("Baza wyczyszczona!");
        window.location.reload();
      } else {
        alert("Błąd podczas czyszczenia bazy");
      }
    } catch (error) {
      console.error("Reset failed:", error);
      alert("Nie udało się wyczyścić bazy");
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-4 w-full sm:w-auto flex-wrap">
        <div className="flex items-center gap-2 bg-white dark:bg-slate-900 px-4 py-2 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
          <label className="text-sm font-bold text-slate-600 dark:text-slate-400">Marketplace:</label>
          <select
            value={marketplace}
            onChange={(e) => setMarketplace(e.target.value)}
            disabled={loading}
            className="px-3 py-1 text-sm font-bold text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="autopunkt">Autopunkt</option>
            <option value="findcar">Findcar.pl</option>
            <option value="vehis">Vehis.pl</option>
          </select>
        </div>
        <div className="flex items-center gap-2 bg-white dark:bg-slate-900 px-4 py-2 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
          <label className="text-sm font-bold text-slate-600 dark:text-slate-400">Ilość ofert:</label>
          <input
            type="number"
            min="1"
            max="500"
            value={limit}
            onChange={(e) => setLimit(e.target.value === "" ? "" : Number(e.target.value))}
            disabled={loading}
            placeholder="Wszystkie"
            className="w-24 px-3 py-1 text-sm font-bold text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <button
          onClick={handleScrape}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white px-6 py-2 rounded-xl font-black transition-all shadow-lg shadow-indigo-500/20 active:scale-95 whitespace-nowrap"
        >
          {loading ? "Przetwarzanie..." : "Uruchom Scraper"}
        </button>
        <button
          onClick={handleReset}
          disabled={loading}
          className="bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-600 dark:text-red-400 px-4 py-2 rounded-xl font-bold transition-all border border-red-200 dark:border-red-800"
        >
          Wyczyść bazę
        </button>
      </div>

      {loading && progress && (
        <div className="bg-white dark:bg-slate-900 px-4 py-3 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2 mb-2">
            <div className="animate-spin h-4 w-4 border-2 border-indigo-600 border-t-transparent rounded-full" />
            <span className="text-sm font-bold text-slate-700 dark:text-slate-300">{progress.status}</span>
          </div>
          {progress.total && progress.total > 0 && (
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${((progress.current || 0) / progress.total) * 100}%` }}
              />
            </div>
          )}
          {progress.total && progress.total > 0 && (
            <p className="text-xs text-slate-500 mt-1 font-medium">
              {progress.current} / {progress.total} ofert
            </p>
          )}
        </div>
      )}
    </div>
  );
}
