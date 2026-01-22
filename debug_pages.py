import requests
import re

def check_page(p):
    url = f"https://findcar.pl/oferty-dealerow?priceType=offer&size=45&sort=createdAt,desc&page={p}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://findcar.pl/"
    }
    response = requests.get(url, headers=headers, timeout=30)
    # ids = set(re.findall(r'publicListingNumber"\s*:\s*"(\d+)"', response.text)) # Original regex
    ids = set(re.findall(r'publicListingNumber":"(\d+)"', response.text)) # Slightly different
    print(f"Page {p}: found {len(ids)} ids")
    return len(ids)

check_page(0)
check_page(1)
check_page(2)
