import requests
import re

def check(ua):
    url = "https://findcar.pl/oferty-dealerow?priceType=offer&size=45&sort=createdAt,desc&page=0"
    headers = {"User-Agent": ua}
    res = requests.get(url, headers=headers)
    ids = re.findall(r'publicListingNumber":"(\d+)"', res.text)
    print(f"UA: {ua[:30]}... -> Found {len(ids)}")

check("Mozilla/5.0")
check("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
check("python-requests/2.31.0")
