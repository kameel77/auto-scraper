import { getVehicles, getStats } from "@/lib/api";
import { ScrapeButton } from "@/components/ScrapeButton";

export default async function Home() {
  const [vehicles, stats] = await Promise.all([
    getVehicles().catch(() => []),
    getStats().catch(() => ({ total_vehicles: 0, total_snapshots: 0, avg_price: 0, unique_brands: 0 }))
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
              Przeglądaj najnowsze oferty z Autopunkt wyselekcjonowane dla Ciebie.
            </p>
          </div>
          <div className="flex gap-4 w-full sm:w-auto">
            <ScrapeButton />
            <div className="flex-1 sm:flex-none bg-white dark:bg-slate-900 px-6 py-4 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
              <p className="text-xs text-indigo-600 dark:text-indigo-400 uppercase font-bold tracking-widest mb-1">Pojazdy / Odczyty</p>
              <p className="text-3xl font-black text-slate-900 dark:text-white tracking-tight">
                {stats.total_vehicles} <span className="text-slate-400 text-xl">/ {stats.total_snapshots}</span>
              </p>
            </div>
            <div className="flex-1 sm:flex-none bg-white dark:bg-slate-900 px-6 py-4 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
              <p className="text-xs text-indigo-600 dark:text-indigo-400 uppercase font-bold tracking-widest mb-1">Średnia Cena</p>
              <p className="text-3xl font-black text-slate-900 dark:text-white tracking-tight">{Math.round(stats.avg_price).toLocaleString()} zł</p>
            </div>
          </div>
        </header>

        {vehicles.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 bg-white dark:bg-slate-900 rounded-3xl border-2 border-dashed border-slate-200 dark:border-slate-800">
            <p className="text-slate-500 text-lg font-medium">Brak danych w bazie. Uruchom scraper, aby zebrać oferty.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10">
            {vehicles.map((car) => {
              const firstImage = car.latest_image;
              return (
                <div key={car.id} className="group bg-white dark:bg-slate-900 rounded-[2rem] overflow-hidden shadow-2xl border border-slate-100 dark:border-slate-800/50 hover:border-indigo-500/30 transition-all duration-500 hover:-translate-y-2">
                  <div className="relative h-64 w-full overflow-hidden">
                    {firstImage ? (
                      <img
                        src={firstImage}
                        alt={`${car.marka} ${car.model}`}
                        className="object-cover w-full h-full group-hover:scale-110 transition-transform duration-700 ease-out"
                      />
                    ) : (
                      <div className="w-full h-full bg-slate-200 flex items-center justify-center text-slate-400">Brak zdjęcia</div>
                    )}
                    <div className="absolute inset-0 bg-black/10 group-hover:bg-black/0 transition-colors duration-500" />
                    <div className="absolute top-6 right-6 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md px-4 py-2 rounded-2xl text-lg font-black shadow-2xl text-slate-900 dark:text-white">
                      {car.latest_price?.toLocaleString()} <span className="text-sm font-bold text-indigo-600">zł</span>
                    </div>
                  </div>

                  <div className="p-8">
                    <div className="mb-6">
                      <h3 className="text-2xl font-black text-slate-900 dark:text-white leading-none mb-2">
                        {car.marka} {car.model}
                      </h3>
                      <p className="text-sm text-slate-400 font-bold uppercase tracking-tighter">{car.wersja || "Standard"}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-6 bg-slate-50 dark:bg-slate-950/50 p-5 rounded-2xl mb-8">
                      <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase font-black tracking-widest mb-1">Rocznik</span>
                        <span className="font-extrabold text-slate-900 dark:text-slate-100">{car.rocznik}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase font-black tracking-widest mb-1">Przebieg</span>
                        <span className="font-extrabold text-slate-900 dark:text-slate-100">{car.latest_mileage?.toLocaleString()} km</span>
                      </div>
                    </div>

                    <div className="flex justify-between items-center gap-4">
                      <div className="flex flex-col min-w-0">
                        <span className="text-[10px] text-slate-400 uppercase font-black tracking-widest mb-0.5">Lokalizacja</span>
                        <span className="text-sm text-slate-600 dark:text-slate-400 font-bold truncate">{car.lokalizacja_miasto}</span>
                      </div>
                      <a
                        href={car.url}
                        target="_blank"
                        className="inline-flex items-center justify-center px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-black rounded-xl transition-all shadow-lg shadow-indigo-500/20 active:scale-95 whitespace-nowrap"
                      >
                        PEŁNA OFERTA
                      </a>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
