import requests
import re

url = "https://findcar.pl/oferty-dealerow?priceType=offer&size=1000&sort=createdAt,desc&page=0"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
response = requests.get(url, headers=headers)
ids = set(re.findall(r'publicListingNumber":"(\d+)"', response.text))
print(f"Size 1000: found {len(ids)} ids")
