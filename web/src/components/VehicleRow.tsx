"use client";

import { useState } from "react";
import { type Vehicle } from "@/lib/api";

function EquipmentBadge({ title, items }: { title: string; items: string | null | undefined }) {
  if (!items) return null;
  return (
    <div className="mb-3">
      <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{title}</p>
      <p className="text-xs text-slate-600 dark:text-slate-300">{items}</p>
    </div>
  );
}

export function VehicleRow({ car }: { car: Vehicle }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <td className="px-6 py-4">
          <div className="flex items-center gap-4">
            {car.latest_image ? (
              <img
                src={car.latest_image}
                alt={`${car.marka} ${car.model}`}
                className="w-16 h-12 object-cover rounded-lg"
              />
            ) : (
              <div className="w-16 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center text-slate-400 text-xs">
                Brak
              </div>
            )}
            <div>
              <p className="font-black text-slate-900 dark:text-white">
                {car.marka} {car.model}
              </p>
              <p className="text-xs text-slate-500 font-medium">{car.wersja || ""}</p>
            </div>
          </div>
        </td>
        <td className="px-6 py-4 font-bold text-slate-700 dark:text-slate-300">
          {car.rocznik}
        </td>
        <td className="px-6 py-4">
          <span className="font-black text-indigo-600">
            {car.latest_price?.toLocaleString()} zł
          </span>
        </td>
        <td className="px-6 py-4 text-slate-600 dark:text-slate-400 hidden md:table-cell">
          {car.latest_mileage?.toLocaleString()} km
        </td>
        <td className="px-6 py-4 text-slate-600 dark:text-slate-400 hidden lg:table-cell">
          {car.lokalizacja_miasto}
        </td>
        <td className="px-6 py-4">
          <a
            href={car.url}
            target="_blank"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center justify-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-black rounded-lg transition-all"
          >
            Oferta
          </a>
        </td>
      </tr>
      {expanded && car.equipment && (
        <tr className="bg-slate-50 dark:bg-slate-800/20">
          <td colSpan={6} className="px-6 py-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <EquipmentBadge title="Technologia" items={car.equipment.wyposazenie_technologia} />
              <EquipmentBadge title="Komfort" items={car.equipment.wyposazenie_komfort} />
              <EquipmentBadge title="Bezpieczeństwo" items={car.equipment.wyposazenie_bezpieczenstwo} />
              <EquipmentBadge title="Wygląd" items={car.equipment.wyposazenie_wyglad} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
