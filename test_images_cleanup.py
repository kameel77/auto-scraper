from scraper.offer_parser import parse_offer

url = "https://autopunkt.pl/samochod/bielsko_biala/kombi/opel/insignia/id/109920"
data = parse_offer(url)

print("--- Data Extracted ---")
print(f"URL: {data['url']}")
print(f"Images (zdjecia):")
if data['zdjecia']:
    for i, img in enumerate(data['zdjecia'].split(' | ')):
        print(f"  {i+1}: {img}")
else:
    print("  None")

# Verification
bad_indicators = ["maps", "staticmap", "svg", "data:", "_nuxt", "google"]
found_bad = False
if data.get('zdjecia'):
    img_list = data['zdjecia'].split(' | ')
    for img in img_list:
        if any(bad in img.lower() for bad in bad_indicators):
            print(f"!!! Error: Found bad image: {img}")
            found_bad = True
    
    if len(img_list) > 1:
        print(f"--- INFO: Extracted {len(img_list)} images ---")
    else:
        print(f"--- WARNING: Only extracted {len(img_list)} image(s) ---")
else:
    print("--- FAILURE: No images extracted at all ---")
