import requests
import re

def check(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    ids = re.findall(r'publicListingNumber":"(\d+)"', res.text)
    print(f"URL: {url}\nFound: {len(ids)}\n")

check("https://findcar.pl/oferty-dealerow?priceType=offer&size=45&sort=createdAt,desc&page=0")
check("https://findcar.pl/oferty-dealerow?priceType=offer&size=45&sort=createdAt,desc&page=1")
check("https://findcar.pl/listings?priceType=offer&size=45&sort=createdAt,desc&page=0")
check("https://findcar.pl/listings?priceType=offer&size=45&sort=createdAt,desc&page=1")
