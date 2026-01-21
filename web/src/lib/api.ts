export interface Vehicle {
    id: number;
    url: string;
    marka: string;
    model: string;
    wersja?: string;
    rocznik: number;
    typ_nadwozia?: string;
    lokalizacja_miasto?: string;
    latest_price: number;
    latest_mileage: number;
    latest_image?: string;
    scraped_at: string;
    equipment?: {
        wyposazenie_technologia?: string;
        wyposazenie_komfort?: string;
        wyposazenie_bezpieczenstwo?: string;
        wyposazenie_wyglad?: string;
    };
}

export interface PriceTrend {
    scraped_at: string;
    price: number;
    mileage: number;
}

export interface Stats {
    total_vehicles: number;
    total_snapshots: number;
    avg_price: number;
    unique_brands: number;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getVehicles(marka?: string): Promise<Vehicle[]> {
    const url = new URL(`${API_BASE_URL}/vehicles`);
    if (marka) url.searchParams.append("marka", marka);

    const res = await fetch(url.toString(), { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch vehicles");
    return res.json();
}

export async function getStats(): Promise<Stats> {
    const res = await fetch(`${API_BASE_URL}/stats`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch stats");
    return res.json();
}

export async function getVehicleTrends(vehicleId: number): Promise<PriceTrend[]> {
    const res = await fetch(`${API_BASE_URL}/vehicles/${vehicleId}/trends`, {
        cache: "no-store",
    });
    if (!res.ok) throw new Error("Failed to fetch vehicle trends");
    return res.json();
}

export async function startScrape(limit: number = 10): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE_URL}/scrape?limit=${limit}`, {
        method: "POST",
    });
    if (!res.ok) throw new Error("Failed to start scrape");
    return res.json();
}
