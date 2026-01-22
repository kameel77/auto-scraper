import requests
import re

url = "https://findcar.pl/oferty-dealerow?priceType=offer&size=45&sort=createdAt,desc&page=0"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
    "Referer": "https://findcar.pl/"
}

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")
    
    # Try finding IDs with slashes
    ids = set(re.findall(r'/listings/(\d+)', response.text))
    print(f"IDs count (regex /listings/): {len(ids)}")
    
    # Try finding IDs in JSON-like structure
    ids2 = set(re.findall(r'publicListingNumber":"(\d+)"', response.text))
    print(f"IDs count (regex publicListingNumber): {len(ids2)}")
    
    # Try finding technical IDs
    ids3 = set(re.findall(r'"listingNumber":"(\d+)"', response.text))
    print(f"IDs count (regex listingNumber): {len(ids3)}")

    if len(ids) > 0: print(f"Sample ids: {list(ids)[:3]}")
    if len(ids2) > 0: print(f"Sample ids2: {list(ids2)[:3]}")
    if len(ids3) > 0: print(f"Sample ids3: {list(ids3)[:3]}")

except Exception as e:
    print(f"Error: {e}")
