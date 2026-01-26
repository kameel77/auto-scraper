import requests
import re

url = "https://findcar.pl/oferty-dealerow?priceType=offer&size=50&sort=createdAt,desc&page=0"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

print(f"Fetching {url}...")
# Use a session to simulate the scraper better
s = requests.Session()
s.headers.update(headers)
resp = s.get(url, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Length: {len(resp.text)}")

# Existing regex
old_pattern = r'/listings/(?:[^"\']*?[-/])?(\d{5,})'
old_matches = re.findall(old_pattern, resp.text)
print(f"Old regex matches: {len(old_matches)}")

# New regex based on browser check
new_pattern = r'/oferty-dealerow/[^"\']*?-(\d{9})(?:\?|#|")'
new_matches = re.findall(new_pattern, resp.text)
print(f"New regex matches: {len(new_matches)}")
if new_matches:
    print(f"Sample IDs: {new_matches[:5]}")

# Try finding publicListingNumber
json_ids = re.findall(r'"publicListingNumber"\s*:\s*"(\d+)"', resp.text)
print(f"JSON matches: {len(json_ids)}")

if not new_matches and not json_ids:
    print("Capturing snippet for manual inspection...")
    # Look for any digit-ending slugs
    slugs = re.findall(r'/oferty-dealerow/[^"\' >]+', resp.text)
    print(f"Found {len(slugs)} slugs. First 5: {slugs[:5]}")
