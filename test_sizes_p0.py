import requests
import re

def check(size, p):
    url = f"https://findcar.pl/oferty-dealerow?priceType=offer&size={size}&sort=createdAt,desc&page={p}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    ids = re.findall(r'publicListingNumber":"(\d+)"', res.text)
    print(f"Size {size}, Page {p} -> Found {len(ids)}")

check(5, 0)
check(10, 0)
check(100, 0)
check(500, 0)
