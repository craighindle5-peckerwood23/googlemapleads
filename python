import googlemaps
import csv
import time

gmaps = googlemaps.Client(key='YOUR_API_KEY')  # Get from Google Cloud

queries = ['restaurant in Los Angeles', 'nail salon in Los Angeles', 'gym Los Angeles']
all_places = []

for query in queries:
    next_page_token = None
    while len(all_places) < 2000:
        if next_page_token:
            time.sleep(2)  # Required delay
            places_result = gmaps.places(query=None, page_token=next_page_token)
        else:
            places_result = gmaps.places(query=query, location='34.0522,-118.2437', radius=32000)
        all_places.extend(places_result['results'])
        next_page_token = places_result.get('next_page_token')
        if not next_page_token:
            break

# Extract name, address, phone, website
with open('la_leads.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Name', 'Address', 'Phone', 'Website'])
    for p in all_places:
        place = gmaps.place(p['place_id'], fields=['name','formatted_address','formatted_phone_number','website'])
        details = place['result']
        writer.writerow([details.get('name'), details.get('formatted_address'), details.get('formatted_phone_number'), details.get('website')])
