"use client";

import { useState, useEffect } from "react";

interface DealerConfig {
  id: number;
  marketplace: string;
  dealer_name: string;
  base_url: string;
  is_active: number;
  created_at: string;
}

export function DealerConfigurator() {
  const [configs, setConfigs] = useState<DealerConfig[]>([]);
  const [dealerName, setDealerName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchConfigs = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/dealer-configs`);
      const data = await res.json();
      setConfigs(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const handleAdd = async () => {
    if (!dealerName || !baseUrl) return;
    setLoading(true);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/dealer-configs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          marketplace: "pewneauto",
          dealer_name: dealerName,
          base_url: baseUrl,
          is_active: 1
        })
      });
      setDealerName("");
      setBaseUrl("");
      fetchConfigs();
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Na pewno usunąć tego dealera?")) return;
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/dealer-configs/${id}`, {
        method: "DELETE"
      });
      fetchConfigs();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden mb-6">
      <div className="p-6">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-4">Ustawienia Dealerów (Pewne Auto)</h2>
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <input 
            type="text" 
            placeholder="Nazwa Dealera (np. Toyota Okęcie)" 
            className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={dealerName}
            onChange={(e) => setDealerName(e.target.value)}
            disabled={loading}
          />
          <input 
            type="text" 
            placeholder="Adres URL (np. https://uzywane.grupasabaj.pl)" 
            className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            disabled={loading}
          />
          <button 
            onClick={handleAdd}
            disabled={loading}
            className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg transition-colors"
          >
            Dodaj
          </button>
        </div>

        {configs.length > 0 ? (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {configs.map((conf) => (
              <li key={conf.id} className="py-3 flex justify-between items-center">
                <div>
                  <span className="font-bold text-slate-900 dark:text-white mr-2">{conf.dealer_name}</span>
                  <span className="text-sm text-slate-500">{conf.base_url}</span>
                </div>
                <button 
                  onClick={() => handleDelete(conf.id)}
                  className="text-red-500 hover:text-red-700 text-sm font-bold"
                >
                  Usuń
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">Brak zdefiniowanych dilerów. Scraper pobierze domyślnie główne pewneauto.pl.</p>
        )}
      </div>
    </div>
  );
}
