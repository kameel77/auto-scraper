"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

export function FilterBar() {
    const router = useRouter();
    const searchParams = useSearchParams();

    // UI selections state
    const [selectedBrand, setSelectedBrand] = useState(searchParams.get("marka") || "");
    const [selectedModel, setSelectedModel] = useState(searchParams.get("model") || "");
    const [yearMin, setYearMin] = useState(searchParams.get("rok_min") || "");
    const [yearMax, setYearMax] = useState(searchParams.get("rok_max") || "");
    const [priceMin, setPriceMin] = useState(searchParams.get("cena_min") || "");
    const [priceMax, setPriceMax] = useState(searchParams.get("cena_max") || "");
    const [selectedCity, setSelectedCity] = useState(searchParams.get("miasto") || "");

    // Dynamic data state
    const [brands, setBrands] = useState<string[]>([]);
    const [models, setModels] = useState<string[]>([]);
    const [cities, setCities] = useState<string[]>([]);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    // Fetch brands and cities on mount
    useEffect(() => {
        const fetchData = async () => {
            try {
                const [brandsRes, citiesRes] = await Promise.all([
                    fetch(`${apiUrl}/brands`),
                    fetch(`${apiUrl}/cities`)
                ]);
                if (brandsRes.ok) setBrands(await brandsRes.json());
                if (citiesRes.ok) setCities(await citiesRes.json());
            } catch (error) {
                console.error("Error fetching initial filter data:", error);
            }
        };
        fetchData();
    }, [apiUrl]);

    // Fetch models when brand changes
    useEffect(() => {
        const fetchModels = async () => {
            if (!selectedBrand) {
                setModels([]);
                return;
            }
            try {
                const res = await fetch(`${apiUrl}/models?marka=${encodeURIComponent(selectedBrand)}`);
                if (res.ok) setModels(await res.json());
            } catch (error) {
                console.error("Error fetching models:", error);
            }
        };
        fetchModels();
    }, [selectedBrand, apiUrl]);

    const updateFilters = (newFilters: Record<string, string>) => {
        const params = new URLSearchParams(searchParams.toString());
        Object.entries(newFilters).forEach(([key, value]) => {
            if (value) {
                params.set(key, value);
            } else {
                params.delete(key);
            }
        });
        router.push(`/?${params.toString()}`);
    };

    const handleClear = () => {
        setSelectedBrand("");
        setSelectedModel("");
        setYearMin("");
        setYearMax("");
        setPriceMin("");
        setPriceMax("");
        setSelectedCity("");
        router.push("/");
    };

    return (
        <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl shadow-sm border border-slate-100 dark:border-slate-800 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Marka & Model */}
                <div className="space-y-4">
                    <div className="flex flex-col gap-2">
                        <label className="text-xs font-black uppercase tracking-widest text-slate-400">Marka</label>
                        <select
                            value={selectedBrand}
                            onChange={(e) => {
                                const val = e.target.value;
                                setSelectedBrand(val);
                                setSelectedModel("");
                                updateFilters({ marka: val, model: "" });
                            }}
                            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 rounded-2xl text-sm font-bold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-mono"
                        >
                            <option value="">Wszystkie marki</option>
                            {brands.map((b) => <option key={b} value={b}>{b}</option>)}
                        </select>
                    </div>
                    <div className="flex flex-col gap-2">
                        <label className="text-xs font-black uppercase tracking-widest text-slate-400">Model</label>
                        <select
                            value={selectedModel}
                            disabled={!selectedBrand}
                            onChange={(e) => {
                                const val = e.target.value;
                                setSelectedModel(val);
                                updateFilters({ model: val });
                            }}
                            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 rounded-2xl text-sm font-bold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-mono disabled:opacity-50"
                        >
                            <option value="">Wszystkie modele</option>
                            {models.map((m) => <option key={m} value={m}>{m}</option>)}
                        </select>
                    </div>
                </div>

                {/* Rocznik */}
                <div className="space-y-4">
                    <label className="text-xs font-black uppercase tracking-widest text-slate-400 block">Rocznik</label>
                    <div className="flex gap-2">
                        <input
                            type="number"
                            placeholder="Od"
                            value={yearMin}
                            onChange={(e) => setYearMin(e.target.value)}
                            onBlur={() => updateFilters({ rok_min: yearMin })}
                            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 rounded-2xl text-sm font-bold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-mono"
                        />
                        <input
                            type="number"
                            placeholder="Do"
                            value={yearMax}
                            onChange={(e) => setYearMax(e.target.value)}
                            onBlur={() => updateFilters({ rok_max: yearMax })}
                            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 rounded-2xl text-sm font-bold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-mono"
                        />
                    </div>
                    <div className="flex flex-col gap-2">
                        <label className="text-xs font-black uppercase tracking-widest text-slate-400">Lokalizacja</label>
                        <select
                            value={selectedCity}
                            onChange={(e) => {
                                const val = e.target.value;
                                setSelectedCity(val);
                                updateFilters({ miasto: val });
                            }}
                            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 rounded-2xl text-sm font-bold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-mono"
                        >
                            <option value="">Wszystkie miasta</option>
                            {cities.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                </div>

                {/* Cena */}
                <div className="space-y-4 md:col-span-2">
                    <label className="text-xs font-black uppercase tracking-widest text-slate-400 block">Cena (PLN)</label>
                    <div className="flex gap-4">
                        <div className="relative flex-1">
                            <input
                                type="number"
                                placeholder="Cena od"
                                value={priceMin}
                                onChange={(e) => setPriceMin(e.target.value)}
                                onBlur={() => updateFilters({ cena_min: priceMin })}
                                className="w-full pl-4 pr-12 py-3 bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 rounded-2xl text-sm font-bold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-mono"
                            />
                            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-black text-slate-400">PLN</span>
                        </div>
                        <div className="relative flex-1">
                            <input
                                type="number"
                                placeholder="Cena do"
                                value={priceMax}
                                onChange={(e) => setPriceMax(e.target.value)}
                                onBlur={() => updateFilters({ cena_max: priceMax })}
                                className="w-full pl-4 pr-12 py-3 bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 rounded-2xl text-sm font-bold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-mono"
                            />
                            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-black text-slate-400">PLN</span>
                        </div>
                    </div>

                    <div className="flex justify-end pt-2">
                        <button
                            onClick={handleClear}
                            className="px-6 py-3 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400 text-xs font-black uppercase tracking-widest rounded-2xl transition-all"
                        >
                            Wyczyść filtry
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
