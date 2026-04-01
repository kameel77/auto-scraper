"use client";

import { useEffect, useState } from "react";
import { getScrapeLogs, ScrapeLog } from "@/lib/api";

export function ScrapeHistory() {
  const [logs, setLogs] = useState<ScrapeLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeProgress, setActiveProgress] = useState<{ status: string; current?: number; total?: number; message?: string; log_id?: number } | null>(null);

  const fetchLogs = async () => {
    try {
      const data = await getScrapeLogs(5);
      setLogs(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    // Setting up a periodic refresh to catch changes if multiple users use it, or when scraping completes.
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Check if there is an active scrape globally from the SSE
    const eventSource = new EventSource(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/scrape/progress`);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.status === "progress" || data.status === "collecting" || data.status === "scraping" || data.status === "running") {
        setActiveProgress(data);
      } else if (data.status === "complete" || data.status === "error") {
        setActiveProgress(data);
        eventSource.close();
        fetchLogs(); // refresh immediately
      } else if (data.status === "idle") {
        setActiveProgress(null);
      }
    };

    return () => {
      eventSource.close();
    };
  }, []);

  if (loading) return <div className="animate-pulse h-20 bg-slate-200 dark:bg-slate-800 rounded-2xl" />;

  if (logs.length === 0 && !activeProgress) return null;

  return (
    <div className="bg-white dark:bg-slate-900 px-6 py-6 rounded-3xl shadow-sm border border-slate-200 dark:border-slate-800 mb-6">
      <h2 className="text-xl font-black text-slate-900 dark:text-white tracking-tight mb-4">
        Ostatnie Scrape'owania
      </h2>
      
      {activeProgress && activeProgress.status !== "idle" && activeProgress.status !== "error" && activeProgress.status !== "complete" && (
        <div className="mb-6 bg-indigo-50 dark:bg-indigo-900/20 px-4 py-3 rounded-xl border border-indigo-100 dark:border-indigo-800/50">
          <div className="flex items-center gap-2 mb-2">
            <div className="animate-spin h-4 w-4 border-2 border-indigo-600 border-t-transparent rounded-full" />
            <span className="text-sm font-bold text-indigo-700 dark:text-indigo-300">Aktywne: {activeProgress.message}</span>
          </div>
          {activeProgress?.total && activeProgress.total > 0 && (
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${((activeProgress.current || 0) / (activeProgress.total || 1)) * 100}%` }}
              />
            </div>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="text-xs font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">
              <th className="pb-3 pr-4">Data Systemowa</th>
              <th className="pb-3 pr-4">Źródło</th>
              <th className="pb-3 pr-4">Pobrane</th>
              <th className="pb-3 pr-4">W bazie</th>
              <th className="pb-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {logs.map((log) => {
              // If this log is currently running based on global active progress it might be out of date
              let statusLabel = log.status;
              let statusColor = "text-slate-500";
              let statusBg = "bg-slate-100 dark:bg-slate-800";
              
              if (activeProgress && activeProgress.log_id === log.id && activeProgress.status !== 'complete' && activeProgress.status !== 'error') {
                 statusLabel = `running (${activeProgress.current}/${activeProgress.total})`;
                 statusColor = "text-indigo-700 dark:text-indigo-300";
                 statusBg = "bg-indigo-100 dark:bg-indigo-900/30";
              } else {
                 if (log.status === "completed") {
                    statusColor = "text-emerald-700 dark:text-emerald-300";
                    statusBg = "bg-emerald-100 dark:bg-emerald-900/30";
                 } else if (log.status === "error") {
                    statusColor = "text-red-700 dark:text-red-300";
                    statusBg = "bg-red-100 dark:bg-red-900/30";
                 } else if (log.status === "running") {
                    statusColor = "text-indigo-700 dark:text-indigo-300";
                    statusBg = "bg-indigo-100 dark:bg-indigo-900/30";
                 }
              }

              return (
                <tr key={log.id} className="text-sm border-slate-100 dark:border-slate-800">
                  <td className="py-3 pr-4 font-medium text-slate-600 dark:text-slate-300">
                    {new Date(log.start_time).toLocaleString("pl-PL")}
                  </td>
                  <td className="py-3 pr-4 font-bold text-slate-800 dark:text-slate-200">
                    {log.marketplace}
                  </td>
                  <td className="py-3 pr-4 text-slate-600 dark:text-slate-300">
                    {log.status === "completed" ? log.vehicles_scraped : "-"}
                  </td>
                  <td className="py-3 pr-4 text-slate-600 dark:text-slate-300">
                    {log.total_vehicles_in_db}
                  </td>
                  <td className="py-3">
                    <span className={`px-2 py-1 rounded-md font-bold text-xs ${statusColor} ${statusBg} truncate max-w-[200px] block`}>
                      {statusLabel}
                      {log.error_message && ` - ${log.error_message}`}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
