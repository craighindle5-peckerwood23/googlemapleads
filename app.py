import os
import csv
import time
import threading
from flask import Flask, render_template, request, send_file, jsonify
from dotenv import load_dotenv
import googlemaps
import pandas as pd

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-me'

# Store scrape status and data globally (for simplicity)
scrape_status = {
    'running': False,
    'progress': 0,
    'total': 0,
    'csv_path': None,
    'error': None
}

def places_to_df(places):
    """Convert raw Google Maps places to a DataFrame"""
    rows = []
    for place in places:
        rows.append({
            'Name': place.get('name', ''),
            'Address': place.get('formatted_address', ''),
            'Phone': place.get('formatted_phone_number', ''),
            'Website': place.get('website', ''),
            'Rating': place.get('rating', ''),
            'Total Reviews': place.get('user_ratings_total', ''),
            'Place ID': place.get('place_id', ''),
        })
    return pd.DataFrame(rows)

def get_place_details(gmaps, place_id, fields):
    """Fetch details for a single place, with retries"""
    for attempt in range(3):
        try:
            details = gmaps.place(place_id, fields=fields)['result']
            return details
        except Exception as e:
            time.sleep(1)
    return {}

def search_and_scrape(gmaps, query, location, target_count):
    """
    Use Google Maps Text Search to find places.
    Because Google returns max 60 results per query, we'll
    use multiple related queries to reach target_count.
    """
    all_places = []
    seen_ids = set()

    # Base query + some variations to get more results
    base_queries = [
        query,
        f"best {query}",
        f"top {query}",
        f"{query} in {location}",
        f"popular {query}",
    ]

    for base_q in base_queries:
        if len(all_places) >= target_count:
            break
        next_page_token = None
        while len(all_places) < target_count:
            try:
                if next_page_token:
                    time.sleep(2)  # required delay
                    result = gmaps.places(query=None, page_token=next_page_token)
                else:
                    result = gmaps.places(query=base_q, location=location)
            except Exception as e:
                print(f"Search error: {e}")
                break

            for place in result.get('results', []):
                pid = place.get('place_id')
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    all_places.append(place)
                    if len(all_places) >= target_count:
                        break

            next_page_token = result.get('next_page_token')
            if not next_page_token:
                break

    print(f"Found {len(all_places)} unique places.")
    return all_places[:target_count]

def run_scrape(query, location, count):
    global scrape_status
    scrape_status['running'] = True
    scrape_status['progress'] = 0
    scrape_status['total'] = count
    scrape_status['error'] = None
    scrape_status['csv_path'] = None

    try:
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            raise Exception("API key not found in .env file")
        gmaps = googlemaps.Client(key=api_key)

        # 1. Search for places (basic data)
        places = search_and_scrape(gmaps, query, location, count)
        scrape_status['total'] = count

        # 2. Enrich with details (phone, website) - this costs $$
        enriched = []
        batch_size = 10  # small batch for status updates
        for i in range(0, len(places), batch_size):
            batch = places[i:i+batch_size]
            for place in batch:
                details = get_place_details(gmaps, place['place_id'],
                                            fields=['formatted_address',
                                                    'formatted_phone_number',
                                                    'website'])
                # Merge details into place
                place.update({k: details[k] for k in details if k not in place})
                enriched.append(place)
                scrape_status['progress'] += 1

        # 3. Convert to DataFrame and save CSV
        df = places_to_df(enriched)
        csv_path = f"leads_{query.replace(' ', '_')}_{int(time.time())}.csv"
        df.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL)
        scrape_status['csv_path'] = csv_path
        scrape_status['running'] = False

    except Exception as e:
        scrape_status['error'] = str(e)
        scrape_status['running'] = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_scrape():
    if scrape_status['running']:
        return jsonify({'error': 'A scrape is already running. Please wait.'}), 400

    query = request.form.get('query', 'restaurant')
    location = request.form.get('location', 'Los Angeles, CA')
    count = int(request.form.get('count', 2000))

    # Cap count for safety
    if count > 2000:
        count = 2000

    thread = threading.Thread(target=run_scrape, args=(query, location, count))
    thread.start()
    return jsonify({'message': 'Scrape started'})

@app.route('/status')
def status():
    return jsonify(scrape_status)

@app.route('/download')
def download():
    if scrape_status['csv_path']:
        return send_file(scrape_status['csv_path'], as_attachment=True)
    return "No file yet", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
