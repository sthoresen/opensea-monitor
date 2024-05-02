import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from datetime import timezone

import logging

# Load environment variables
load_dotenv()

# Environment variables
OPENSEA_API_KEY = os.getenv('OPENSEA_API_KEY')  # Ensure to set this in your .env file

# Headers required by OpenSea
headers = {
    "accept": "application/json",
    "x-api-key": OPENSEA_API_KEY
}


def extract_floor_price(json_response):
    # Check if 'listings' is in the JSON and if it has at least one item
    if 'listings' in json_response and len(json_response['listings']) > 0:
        # Extract the first item from 'listings'
        listing = json_response['listings'][0]
        # Navigate through the nested dictionaries to get the 'value'
        price_str = listing.get('price', {}).get('current', {}).get('value', None)
        divisor = listing.get('price', {}).get('current', {}).get('decimals', None)
        if price_str is not None:
            try:
                # Convert the price value from string to its correct numerical type
                price = float(price_str)
                divisor = int(divisor)
                return price/(10**divisor)
            except ValueError:
                # Handle the case where the price is not a valid number
                print("The price value is not a valid number.")
        else:
            print("Price information is missing.")
    else:
        print("No listings found in the JSON response.")
    return None


def extract_best_offer(json_response):
    # Assume 'offers' is the key where all offers are stored
    if 'offers' not in json_response or len(json_response['offers']) == 0:
        print("No offers found.")
        return 0

    highest_offer = {"value": 0, "currency": ""}
    n = len(json_response['offers'])
    print(f'Found {n} offers.')
    for offer in json_response['offers']:
        value_str = offer.get('price', {}).get('value', '0')
        currency = offer.get('price', {}).get('currency', 'Unknown')
        divisor = offer.get('price', {}).get('decimals', 0)

        try:
            # Convert the string value to a float for comparison
            value = float(value_str)/(10**int(divisor))
        except ValueError:
            print("Invalid value for offer:", value_str)
            continue

        print(f"Offer: {value} {currency}")

        if value > highest_offer['value']:
            highest_offer['value'] = value
            highest_offer['currency'] = currency

    # Returning the highest offer found
    return highest_offer

def extract_sales_events(json_response):
    most_recent_sale = None

    for event in json_response.get('asset_events', []):
        if event['event_type'] == 'sale':
            # Extract relevant information
            price = event.get('payment', {}).get('quantity', 'Unknown')
            divisor = event.get('payment', {}).get('decimals', 0)
            closing_date = event.get('closing_date', 'Unknown')
            order_hash = event.get('order_hash', 'Unknown')
            
            # Initialize most_recent_sale if it's None or update if the current event is more recent
            if most_recent_sale is None or closing_date > most_recent_sale['closing_date']:
                most_recent_sale = {
                    'closing_date': closing_date,
                    'order_hash': order_hash,
                    'price': float(price)/(10**int(divisor))
                }
            else:
                #print
                sale = {
                    'closing_date': closing_date,
                    'order_hash': order_hash,
                    'price': float(price)/(10**int(divisor))
                }
                print(sale)


    if most_recent_sale:
        # Printing the details of the most recent sale
        print(f"Most Recent Sale - Price: {most_recent_sale['price']}, Closing Date: {most_recent_sale['closing_date']}, Order Hash: {most_recent_sale['order_hash']}")
        date_readable = f"Closing Date: {datetime.utcfromtimestamp(most_recent_sale['closing_date']).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        return f"Latest sale= {most_recent_sale['price']}ETH, at date {date_readable}"
    else:
        print("No sale events found.")
        return None


# Function to fetch collection stats
def fetch_collection_stats(collection_slug):
    nlistings = 1
    noffers = 100

    floor_price, best_offer, last_sale = None, None, None

    url = f"https://api.opensea.io/api/v2/listings/collection/{collection_slug}/best?limit={nlistings}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        #print(data)
        floor_price = extract_floor_price(data)
        print(f'floor_price={floor_price}')

    else:
        print(f"Failed to fetch data: {response.status_code}")
        return None
    
    url = f"https://api.opensea.io/api/v2/offers/collection/{collection_slug}/all?limit={noffers}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        #print(data)


        best_offer = extract_best_offer(data)['value']
        print(f'best_offer = {best_offer}')

    else:
        print(f"Failed to fetch data: {response.status_code}")
        return None
    
    url = f"https://api.opensea.io/api/v2/events/collection/{collection_slug}?event_type=sale&limit=3"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        #print(data)

        last_sale = extract_sales_events(data)
        print(f'last_sale = {last_sale}')

    else:
        print(f"Failed to fetch data: {response.status_code}")
        return None
    
    return {
        'floor_price': floor_price,
        'best_offer': best_offer,
        'last_sale': last_sale
    }
    



# Function to send an email (placeholder)
def send_email(stats, old_stats):
    lines = []
    if stats['floor_price'] != old_stats['floor_price']:
        lines.append(f"Floor price change! {old_stats['floor_price']} -> {stats['floor_price']}")

    if stats['last_sale'] != old_stats['last_sale']:
        lines.append(f"New sale detected! {stats['last_sale']}")

    if stats['best_offer'] != old_stats['best_offer']:
        lines.append(f"Best offer change! {old_stats['best_offer']} -> {stats['best_offer']}")

    lines.append(f'Sending email at {datetime.now()}')
    lines.append('https://opensea.io/collection/99originals')

    print('Email: ')
    for l in lines:
        print(l)
    return lines


# Main function
def main():
    utc_timestamp = datetime.utcnow().replace(
        tzinfo=timezone.utc).isoformat()

    if True:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function ran at (mon.py file!) %s', utc_timestamp)


    collection_slug = "99originals"
    stats = fetch_collection_stats(collection_slug)

    print(f'stats = {stats}')

    last_stats = {
        'floor_price': 18.42,
        'best_offer': 10.0,
        'last_sale': 'Latest sale= 71.59ETH, at date Closing Date: 2024-03-30 23:46:59 UTC'
    }

    if not stats:
        return

    if stats != last_stats:
        # Placeholder for change detection logic
        send_email(stats, last_stats)
        # Here you would compare 'stats' with previously fetched data
        # and call 'send_email' if changes are detected

if __name__ == "__main__":
    main()
