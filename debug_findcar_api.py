import requests
import re
import json

url = "https://findcar.pl/api/listings?priceType=offer&size=45&sort=createdAt,desc&page=0"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://findcar.pl/oferty-dealerow"
}

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])
        print(f"Found {len(items)} items in JSON API")
        if items:
            print(f"Sample item ID: {items[0].get('publicListingNumber')}")
            print(f"Total elements available: {data.get('totalElements')}")
except Exception as e:
    print(f"Error: {e}")
