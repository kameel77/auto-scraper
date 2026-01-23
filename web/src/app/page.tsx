import { getVehicles, getStats } from "@/lib/api";
import { ScrapeButton } from "@/components/ScrapeButton";
import { VehicleRow } from "@/components/VehicleRow";
import { FilterBar } from "@/components/FilterBar";
import { Suspense } from "react";

export const revalidate = 0;

export default async function Home({
    searchParams,
}: {
    searchParams: Promise<{
        marka?: string;
        model?: string;
        rok_min?: string;
        rok_max?: string;
        cena_min?: string;
        cena_max?: string;
        miasto?: string;
    }>;
}) {
    const filters = await searchParams;
    const [vehicles, stats] = await Promise.all([
        getVehicles(filters as any).catch(() => []),
        getStats().catch(() => ({
            total_vehicles: 0,
            total_snapshots: 0,
            avg_price: 0,
            unique_brands: 0,
        })),
    ]);

    return (
        <main className="min-h-screen bg-slate-50 dark:bg-slate-950 p-8 sm:p-12">
            <div className="max-w-7xl mx-auto">
                <header className="mb-12 flex flex-col sm:flex-row justify-between items-start sm:items-end gap-6">
                    <div className="space-y-2">
                        <h1 className="text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white">
                            Auto-Scraper <span className="text-indigo-600">Dashboard</span>
                        </h1>
                        <p className="text-lg text-slate-500 font-medium tracking-wide">
                            Przeglądaj najnowsze oferty z wielu źródeł wyselekcjonowane dla Ciebie.
                        </p>
                    </div>
                    <div className="flex gap-4 w-full sm:w-auto flex-wrap">
                        <a
                            href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
                                }/export/csv/car-scout`}
                            target="_blank"
                            className="inline-flex items-center justify-center px-6 py-3 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-sm font-black rounded-xl transition-all border border-slate-200 dark:border-slate-700"
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
                            CSV Car Scout
                        </a>
                        <a
                            href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
                                }/export/csv`}
                            target="_blank"
                            className="inline-flex items-center justify-center px-6 py-3 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-sm font-black rounded-xl transition-all border border-slate-200 dark:border-slate-700"
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
                            Export CSV
                        </a>
                        <ScrapeButton />
                        <div className="flex-1 sm:flex-none bg-white dark:bg-slate-900 px-6 py-4 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
                            <p className="text-xs text-indigo-600 dark:text-indigo-400 uppercase font-bold tracking-widest mb-1">
                                Pojazdy / Odczyty
                            </p>
                            <p className="text-3xl font-black text-slate-900 dark:text-white tracking-tight">
                                {stats.total_vehicles}{" "}
                                <span className="text-slate-400 text-xl">
                                    / {stats.total_snapshots}
                                </span>
                            </p>
                        </div>
                        <div className="flex-1 sm:flex-none bg-white dark:bg-slate-900 px-6 py-4 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
                            <p className="text-xs text-indigo-600 dark:text-indigo-400 uppercase font-bold tracking-widest mb-1">
                                Średnia Cena
                            </p>
                            <p className="text-3xl font-black text-slate-900 dark:text-white tracking-tight">
                                {Math.round(stats.avg_price).toLocaleString()} zł
                            </p>
                        </div>
                    </div>
                </header>

                <Suspense fallback={<div className="mb-6 h-12 animate-pulse bg-slate-200 dark:bg-slate-800 rounded-xl" />}>
                    <div className="mb-6">
                        <FilterBar />
                    </div>
                </Suspense>

                {vehicles.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 bg-white dark:bg-slate-900 rounded-3xl border-2 border-dashed border-slate-200 dark:border-slate-800">
                        <p className="text-slate-500 text-lg font-medium">
                            {filters.marka
                                ? `Brak ofert dla marki "${filters.marka}".`
                                : "Brak danych w bazie. Uruchom scraper, aby zebrać oferty."}
                        </p>
                    </div>
                ) : (
                    <div className="bg-white dark:bg-slate-900 rounded-3xl shadow-xl border border-slate-100 dark:border-slate-800/50 overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead className="bg-slate-50 dark:bg-slate-950/50 border-b border-slate-100 dark:border-slate-800">
                                    <tr className="text-left text-xs font-black text-slate-400 uppercase tracking-widest">
                                        <th className="px-6 py-4">Pojazd</th>
                                        <th className="px-6 py-4">Rok</th>
                                        <th className="px-6 py-4">Cena</th>
                                        <th className="px-6 py-4 hidden md:table-cell">
                                            Przebieg
                                        </th>
                                        <th className="px-6 py-4 hidden lg:table-cell">
                                            Lokalizacja
                                        </th>
                                        <th className="px-6 py-4"></th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                    {vehicles.map((car) => (
                                        <VehicleRow key={car.id} car={car} />
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </main>
    );
}
