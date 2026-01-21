"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

const BRANDS = [
    "Audi",
    "BMW",
    "Citroën",
    "Dacia",
    "Fiat",
    "Ford",
    "Honda",
    "Hyundai",
    "Jaguar",
    "Jeep",
    "Kia",
    "Land Rover",
    "Lexus",
    "Mazda",
    "Mercedes-Benz",
    "Mini",
    "Nissan",
    "Opel",
    "Peugeot",
    "Porsche",
    "Renault",
    "Seat",
    "Skoda",
    "Smart",
    "Subaru",
    "Suzuki",
    "Tesla",
    "Toyota",
    "Volkswagen",
    "Volvo",
];

export function FilterBar() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [searchTerm, setSearchTerm] = useState(searchParams.get("marka") || "");

    const createQueryString = useCallback(
        (name: string, value: string) => {
            const params = new URLSearchParams(searchParams.toString());
            if (value) {
                params.set(name, value);
            } else {
                params.delete(name);
            }
            return params.toString();
        },
        [searchParams]
    );

    const handleBrandChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const value = e.target.value;
        setSearchTerm(value);
        const queryString = createQueryString("marka", value);
        router.push(`/?${queryString}`);
    };

    const handleClear = () => {
        setSearchTerm("");
        router.push("/");
    };

    return (
        <div className="flex flex-wrap gap-3 items-center">
            <select
                value={searchTerm}
                onChange={handleBrandChange}
                className="px-4 py-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-medium text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
            >
                <option value="">Wszystkie marki</option>
                {BRANDS.map((brand) => (
                    <option key={brand} value={brand}>
                        {brand}
                    </option>
                ))}
            </select>
            {searchTerm && (
                <button
                    onClick={handleClear}
                    className="px-4 py-2.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400 text-sm font-medium rounded-xl transition-all"
                >
                    Wyczyść
                </button>
            )}
        </div>
    );
}
