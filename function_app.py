import logging
import azure.functions as func
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity
from azure.common import AzureHttpError
from mailjet_rest import Client
import requests
from datetime import datetime
from datetime import timezone
from dotenv import load_dotenv
import os

load_dotenv()
def get_env_variable(name):
    """Retrieve an environment variable and show a user-friendly error if it's not found."""
    try:
        return os.environ[name]
    except KeyError:
        error_message = f"Required environment variable '{name}' not set. Please ensure it is defined in .env"
        raise EnvironmentError(error_message)
    
MIN_OFFER_CHANGE = 0.5
OPENSEA_API_KEY = get_env_variable('OPENSEA_API_KEY')
MAILJET_API_KEY = get_env_variable('MAILJET_API_KEY')
MAILJET_SECRET_KEY= get_env_variable('MAILJET_SECRET_KEY')
MAIL_FROM = get_env_variable('MAIL_FROM')
MAIL_TO = get_env_variable('MAIL_TO')
MAIL_TO_NAME = get_env_variable('MAIL_TO_NAME')
STORAGE_ACCOUNT = get_env_variable('STORAGE_ACCOUNT')
STORAGE_ACCOUNT_KEY = get_env_variable('STORAGE_ACCOUNT_KEY')
TABLE_NAME = get_env_variable('TABLE_NAME')
PARTITION_KEY = get_env_variable('PARTITION_KEY')

mailjet = Client(auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY), version='v3.1')
# Headers required by OpenSea
headers = {
    "accept": "application/json",
    "x-api-key": OPENSEA_API_KEY
}
NAME_FROM_DEV = "Lighthouse test service"
NAME_FROM_PROD = "Lighthouse production"


# Initialize Azure Table Service
table_service = TableService(account_name=STORAGE_ACCOUNT, account_key=STORAGE_ACCOUNT_KEY)
table_name = TABLE_NAME
partition_key = PARTITION_KEY
row_key = '1'

app = func.FunctionApp()

@app.schedule(schedule="0/10 * * * * *", arg_name="myTimer", run_on_startup=True,
              use_monitor=False) 
def timer_trigger_alp(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due! alp')

    logging.info('Python timer trigger function executed. alp is alive!')
    old_floor, old_best_offer, old_sale = read_last_data()
    collection_slug = "99originals"
    stats = fetch_collection_stats(collection_slug)
    if stats == None:
        logging.error('Failed to get all data from fetch_collection_stats. Cancelling operations.')
        return

    floor = str(stats['floor'])
    best_offer = str(stats['best_offer'])
    last_sale = str(stats['last_sale'])

    logging.info(f'old best offer: {old_best_offer}')
    logging.info(f'best_offer: {best_offer}')
    offer_dif = abs(float(best_offer)-float(old_best_offer))
    logging.info(f'offer dif = {offer_dif}')

    if old_floor == None:
        logging.info('No prior data found. Writing fetched api data')
        update_data(floor, best_offer, last_sale)
    elif offer_dif >= MIN_OFFER_CHANGE:
        logging.info('Change detected!. Writing fetched api data')
        update_data(floor, best_offer, last_sale)
    elif old_floor != floor or old_sale != last_sale:
        logging.info('Change detected!. Writing fetched api data')
        update_data(floor, best_offer, last_sale)
    elif offer_dif > 0.001:
        logging.info('Minor offer change detected. Updating data, but not sending email')
        update_data(floor, best_offer, last_sale)
        logging.info('Exiting function gracefully')
        return
    else:
        logging.info('No change detected. Exiting function gracefully')
        return

    logging.info('Composing and sending email')
    old_stats = {
        'floor': old_floor,
        'best_offer': old_best_offer,
        'last_sale': old_sale
    }
    subject, text = compose_email(stats, old_stats)
    send_mail(text, subject, dev=False)
    logging.info('Exiting function gracefully after having sent the mail.')

def compose_email(stats, old_stats):
    lines = []
    subject = 'Lighthouse'
    if str(stats['floor']) != str(old_stats['floor']):
        lines.append(f"<p>Floor price change! {old_stats['floor']} -> {stats['floor']}</p>")
        subject = subject + ": Floor price change"

    if stats['last_sale'] != old_stats['last_sale']:
        lines.append(f"<p>New sale detected! {stats['last_sale']}</p>")
        if len(subject) > 15:
            subject = subject + " & new sale"
        else:
            subject = subject + ": New sale"

    if str(stats['best_offer']) != str(old_stats['best_offer']):
        lines.append(f"<p>Best offer change! {old_stats['best_offer']} -> {stats['best_offer']}</p>")
        if len(subject) > 15:
            subject = subject + " & best offer change"
        else:
            subject = subject + ": Best offer change"

    lines.append(f"<p>Sending email at {datetime.now()}</p>")
    lines.append("<a href='https://opensea.io/collection/99originals'>https://opensea.io/collection/99originals</a>")

    text = ''.join(lines)
    return subject, text


def send_mail(text, subject, dev=False):
    data = {
        'Messages': [
            {
            "From": {
                "Email": MAIL_FROM,
                "Name": NAME_FROM_PROD if not dev else NAME_FROM_DEV
            },
            "To": [
                {
                "Email": MAIL_TO,
                "Name": MAIL_TO_NAME
                }
            ],
            "Subject": subject,
            "HTMLPart": text,
            }
        ]
    }

    result = mailjet.send.create(data=data)
    logging.info(f'Sent mail! Code:{result.status_code}')


def read_last_data():
    try:
        entity = table_service.get_entity(table_name, partition_key, row_key)
        logging.info(f"Retrieved values: floor={entity.floor}, best_offer={entity.best_offer}, last_sale={entity.last_sale}")
        return entity.floor, entity.best_offer, entity.last_sale
    except AzureHttpError as e:
        if e.status_code == 404:  # Entity not found
            logging.warn("No data found for the specified PartitionKey and RowKey")
        else:
            logging.error(f"An error occurred when reading data: {e}")
        # Return None or default values if the entity doesn't exist
        return None, None, None

def update_data(floor, best_offer, last_sale):
    # Define the entity with your values
    entity = {
        'PartitionKey': partition_key,
        'RowKey': row_key,
        'floor': floor,
        'best_offer': best_offer,
        'last_sale': last_sale,
    }
    
    # Insert or replace the entity in the table
    table_service.insert_or_replace_entity(table_name, entity)
    logging.info("Entity updated with new data.")

# Function to fetch collection stats
def fetch_collection_stats(collection_slug):
    nlistings = 1
    noffers = 100

    floor_price, best_offer, last_sale = None, None, None

    url = f"https://api.opensea.io/api/v2/listings/collection/{collection_slug}/best?limit={nlistings}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        floor_price = extract_floor_price(data)
    else:
        logging.error(f"Failed to fetch floor data: {response.status_code}")
        return None
    
    url = f"https://api.opensea.io/api/v2/offers/collection/{collection_slug}/all?limit={noffers}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        best_offer = extract_best_offer(data)['value']

    else:
        logging.error(f"Failed to fetch best_offer data: {response.status_code}")
        return None
    
    url = f"https://api.opensea.io/api/v2/events/collection/{collection_slug}?event_type=sale&limit=3"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        last_sale = extract_sales_events(data)
    else:
        logging.error(f"Failed to fetch sale data: {response.status_code}")
        return None
    
    return {
        'floor': floor_price,
        'best_offer': best_offer,
        'last_sale': last_sale
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
                logging.error("The price value is not a valid number.")
        else:
            logging.error("Price information is missing.")
    else:
        logging.error("No listings found in the JSON response.")
    return None

def extract_best_offer(json_response):
    # Assume 'offers' is the key where all offers are stored
    if 'offers' not in json_response or len(json_response['offers']) == 0:
        logging.warn("No offers found.")
        return 0

    highest_offer = {"value": 0, "currency": ""}
    n = len(json_response['offers'])
    logging.info(f'Found {n} offers.')
    for offer in json_response['offers']:
        value_str = offer.get('price', {}).get('value', '0')
        currency = offer.get('price', {}).get('currency', 'Unknown')
        divisor = offer.get('price', {}).get('decimals', 0)

        try:
            # Convert the string value to a float for comparison
            value = float(value_str)/(10**int(divisor))
        except ValueError:
            logging.warn("Invalid value for offer:", value_str)
            continue

        logging.info(f"Offer: {value} {currency}")

        if value > highest_offer['value']:
            highest_offer['value'] = value
            highest_offer['currency'] = currency

    # Returning the highest offer found
    logging.info(f"Highest offer: {highest_offer['value']} {highest_offer['currency']}")
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

    if most_recent_sale:
        # Logging the details of the most recent sale
        logging.info(f"Most Recent Sale - Price: {most_recent_sale['price']}, Closing Date: {most_recent_sale['closing_date']}, Order Hash: {most_recent_sale['order_hash']}")
        date_readable = f"Closing Date: {datetime.utcfromtimestamp(most_recent_sale['closing_date']).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        return f"Latest sale= {most_recent_sale['price']}ETH, at date {date_readable}"
    else:
        logging.error("No sale events found")
        return None
    