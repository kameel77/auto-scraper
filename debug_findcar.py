import requests
import re

url = "https://findcar.pl/oferty-dealerow?priceType=offer&size=45&sort=createdAt,desc&page=1"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
    "Referer": "https://findcar.pl/"
}

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Content length: {len(response.text)}")
    
    ids = set(re.findall(r'/listings/(\d{6,})', response.text))
    print(f"IDs count (regex 1): {len(ids)}")
    
    if not ids:
        ids = set(re.findall(r'"publicListingNumber"\s*:\s*"(\d+)"', response.text))
        print(f"IDs count (regex 2): {len(ids)}")
    
    if not ids:
        with open("findcar_debug.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("No IDs found. Saved HTML to findcar_debug.html")
    else:
        print(f"First 5 IDs: {list(ids)[:5]}")

except Exception as e:
    print(f"Error: {e}")
