import requests
import re

def check(size, p):
    url = f"https://findcar.pl/oferty-dealerow?priceType=offer&size={size}&sort=createdAt,desc&page={p}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    ids = re.findall(r'publicListingNumber":"(\d+)"', res.text)
    print(f"Size {size}, Page {p} -> Found {len(ids)}")

for p in range(5):
    check(45, p)

check(45, 45)
check(45, 90)
check(1000, 0)
