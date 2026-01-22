import requests
import re

url = "https://findcar.pl/oferty-dealerow?priceType=offer&size=45&sort=createdAt,desc&page=0"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
response = requests.get(url, headers=headers)
content = response.text

# Find anything that looks like publicListingNumber
matches = re.findall(r'publicListingNumber.{0,20}', content)
print(f"Matches: {matches[:5]}")

ids = re.findall(r'publicListingNumber\\\\":\\\\"(\d+)\\\\"', content)
print(f"Escaped IDs: {len(ids)}")

ids2 = re.findall(r'publicListingNumber":"(\d+)"', content)
print(f"Direct IDs: {len(ids2)}")
