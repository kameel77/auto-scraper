import requests
import re

def check(p):
    url = f"https://findcar.pl/oferty-dealerow?priceType=offer&size=45&sort=createdAt,desc&page={p}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    res = requests.get(url, headers=headers)
    ids = re.findall(r'publicListingNumber":"(\d+)"', res.text)
    print(f"Page/Offset {p}: Found {len(ids)}")

check(0)
check(45)
check(90)
