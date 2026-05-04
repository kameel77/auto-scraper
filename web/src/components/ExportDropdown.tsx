"use client";

import { useState, useRef, useEffect } from "react";

interface ExportDropdownProps {
    sources: string[];
    apiBaseUrl: string;
}

export function ExportDropdown({ sources, apiBaseUrl }: ExportDropdownProps) {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    // Close dropdown on outside click
    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, []);

    const buildUrl = (format: "csv" | "car-scout" | "car-scout-archive", source?: string) => {
        let path = "";
        if (format === "csv") path = "/export/csv";
        else if (format === "car-scout") path = "/export/csv/car-scout";
        else if (format === "car-scout-archive") path = "/export/csv/car-scout/archive";
        
        const url = new URL(`${apiBaseUrl}${path}`);
        if (source) url.searchParams.append("source", source);
        return url.toString();
    };

    const allSources = ["all", ...Array.from(new Set(["vehis", ...sources]))];

    return (
        <div className="relative" ref={ref}>
            <button
                onClick={() => setOpen(!open)}
                className="inline-flex items-center justify-center px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-black rounded-xl transition-all shadow-lg shadow-indigo-500/25"
            >
                <svg
                    className="w-4 h-4 mr-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                </svg>
                Pobierz CSV
                <svg
                    className={`w-4 h-4 ml-2 transition-transform ${open ? "rotate-180" : ""}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 9l-7 7-7-7"
                    />
                </svg>
            </button>

            {open && (
                <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="px-4 py-3 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
                        <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">
                            Wybierz źródło
                        </p>
                    </div>
                    <div className="max-h-[450px] overflow-y-auto">
                        {allSources.map((source) => {
                            const label = source === "all" ? "🌐 Wszystkie źródła" : source;
                            const sourceParam = source === "all" ? undefined : source;
                            return (
                                <div
                                    key={source}
                                    className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 last:border-b-0 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                                >
                                    <p className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2">
                                        {label}
                                    </p>
                                    <div className="flex flex-col gap-2">
                                        <div className="flex gap-2">
                                            <a
                                                href={buildUrl("car-scout", sourceParam)}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                onClick={() => setOpen(false)}
                                                title="Tylko aktualne oferty z ostatniego pobrania"
                                                className="flex-1 text-center px-3 py-1.5 bg-indigo-50 dark:bg-indigo-900/30 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 text-[10px] font-black rounded-lg transition-colors leading-tight flex items-center justify-center"
                                            >
                                                Car Scout CSV
                                            </a>
                                            <a
                                                href={buildUrl("csv", sourceParam)}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                onClick={() => setOpen(false)}
                                                className="flex-1 text-center px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 text-[10px] font-black rounded-lg transition-colors leading-tight flex items-center justify-center"
                                            >
                                                Zwykły CSV
                                            </a>
                                        </div>
                                        <a
                                            href={buildUrl("car-scout-archive", sourceParam)}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            onClick={() => setOpen(false)}
                                            title="Wszystkie historyczne i aktualne oferty"
                                            className="w-full text-center px-3 py-1.5 bg-amber-50 dark:bg-amber-900/20 hover:bg-amber-100 dark:hover:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-[10px] font-black rounded-lg transition-colors border border-amber-100 dark:border-amber-900/30"
                                        >
                                            Archiwum Car Scout CSV
                                        </a>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
