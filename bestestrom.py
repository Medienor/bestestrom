import requests
import json
from datetime import datetime, timedelta
from statistics import mean  # Add this import
from weds import webflow_bearer_token
from collections import defaultdict
from requests.auth import HTTPBasicAuth

STROMPRIS_USERNAME = 'josef@medienor.no'
STROMPRIS_PASSWORD = '3mXKRl0xVP'
STROMPRIS_BASE_URL = "https://www.strompris.no/strom-product-ms/feeds/"
HVAKOSTER_BASE_URL = "https://www.hvakosterstrommen.no/api/v1/prices"

# Constants
COLLECTION_ID = "66a9fdc25b8c5ae672bad074"
BASE_URL = "https://api.webflow.com/v2"


def get_hvakoster_price(date):
    url = f"{HVAKOSTER_BASE_URL}/{date.year}/{date.strftime('%m-%d')}_NO1.json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return mean([hour['NOK_per_kWh'] for hour in data])
    else:
        print(f"Failed to fetch hvakosterstrommen data for {date.strftime('%Y-%m-%d')}")
        return None
    
def get_strompris_data():
    current_date = datetime.now().strftime("%d-%m-%Y")
    url = f"{STROMPRIS_BASE_URL}{current_date}.json"
    response = requests.get(url, auth=HTTPBasicAuth(STROMPRIS_USERNAME, STROMPRIS_PASSWORD))
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch strompris data for {current_date}")
        return None    

def get_cheapest_companies():
    def get_data_for_date(date):
        url = f"{STROMPRIS_BASE_URL}{date.strftime('%d-%m-%Y')}.json"
        response = requests.get(url, auth=HTTPBasicAuth(STROMPRIS_USERNAME, STROMPRIS_PASSWORD))
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch strompris data for {date.strftime('%d-%m-%Y')}")
            return None

    def process_data(data, month):
        company_prices = defaultdict(lambda: defaultdict(list))
        for company in data:
            for product in company.get('products', []):
                if (product.get('productType') == 'Timespot' and
                    any(area.get('region') == 'regionNO1' for area in product.get('productArea', []))):
                    company_prices[company['companyName']][month].append({
                        'addon_price': float(product.get('addonPrice', 0)),
                        'monthly_fee': float(product.get('monthlyFee', 0)),
                    })
        return company_prices

    def calculate_monthly_prices(all_company_prices, hvakoster_prices):
        monthly_prices = {}
        for company, months_data in all_company_prices.items():
            if all(month in months_data for month in range(1, 5)):  # Check if company has data for all 4 months
                monthly_prices[company] = {}
                for month in range(1, 5):
                    month_prices = months_data[month]
                    if month_prices:
                        avg_addon_price = mean([p['addon_price'] for p in month_prices])
                        monthly_fee = month_prices[0]['monthly_fee']  # Assume monthly fee is constant
                        hvakoster_price = hvakoster_prices[month]
                        if hvakoster_price is not None:
                            total_price = (avg_addon_price + hvakoster_price) * 1333.33 + monthly_fee
                            monthly_prices[company][month] = total_price
                        else:
                            monthly_prices[company][month] = None
                    else:
                        monthly_prices[company][month] = None
        return monthly_prices

    # Get data for the last 4 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)
    current_date = start_date

    all_company_prices = defaultdict(lambda: defaultdict(list))
    hvakoster_prices = {1: [], 2: [], 3: [], 4: []}

    for month in range(1, 5):
        for _ in range(30):  # Approximately 30 days per month
            if current_date <= end_date:
                strompris_data = get_data_for_date(current_date)
                if strompris_data:
                    company_prices = process_data(strompris_data, month)
                    for company, months_data in company_prices.items():
                        all_company_prices[company][month].extend(months_data[month])
                
                hvakoster_price = get_hvakoster_price(current_date)
                if hvakoster_price:
                    hvakoster_prices[month].append(hvakoster_price)
            
            current_date += timedelta(days=1)

    # Calculate average hvakosterstrommen prices for each month
    for month in hvakoster_prices:
        if hvakoster_prices[month]:
            hvakoster_prices[month] = mean(hvakoster_prices[month])
        else:
            hvakoster_prices[month] = None

    # Calculate monthly prices
    monthly_prices = calculate_monthly_prices(all_company_prices, hvakoster_prices)

    # Sort companies by average price across all months
    sorted_companies = sorted(monthly_prices.items(), 
                              key=lambda x: mean([p for p in x[1].values() if p is not None]) if any(p is not None for p in x[1].values()) else float('inf'))
    
    return sorted_companies[:5], monthly_prices

def get_average_electricity_price():
    today = datetime.now().strftime("%Y/%m-%d")
    url = f"https://www.hvakosterstrommen.no/api/v1/prices/{today}_NO1.json"
    response = requests.get(url)
    data = response.json()
    
    prices = [hour['NOK_per_kWh'] for hour in data]
    average_price = mean(prices)
    
    print(f"Average electricity price: {average_price:.5f} NOK/kWh")
    return average_price

def update_winner_power_hero(total_deals, sorted_deals, top_5_cheapest, monthly_prices):
    POWER_HERO_COLLECTION_ID = "66aa4273b55e6852ff204cb7"
    POWER_HERO_ITEM_ID = "66aa427d5426ae4873c0271c"
    
    current_date = datetime.now()
    current_month = current_date.strftime("%B")
    current_year = current_date.year
    
    norwegian_months = {
        "January": "januar", "February": "februar", "March": "mars",
        "April": "april", "May": "mai", "June": "juni",
        "July": "juli", "August": "august", "September": "september",
        "October": "oktober", "November": "november", "December": "desember"
    }
    current_month_norwegian = norwegian_months.get(current_month, current_month)
    
    # Get the top 5 deal IDs
    top_5_ids = [deal['id'] for deal in sorted_deals[:5]]
    
    # Get company info
    company_info = get_company_info()
    
    payload = {
        "isArchived": False,
        "isDraft": False,
        "fieldData": {
            "name": "Winner Power Hero",
            "slug": "winner-power-hero",
            "h1": f"Beste strømavtale {current_month_norwegian} {current_year}",
            "h2": f"Vi har sammenlignet {total_deals} strømavtaler og funnet frem de beste og billigste avtalene for deg i {current_month_norwegian} {current_year}.",
            "top10list": top_5_ids,
        }
    }
    
    # Add data for top 5 cheapest companies
    for i, (company, _) in enumerate(top_5_cheapest, 1):
        payload["fieldData"][f"winner-{i}-name"] = company
        for month in range(1, 5):
            monthly_price = monthly_prices[company][month]
            payload["fieldData"][f"winner-{i}-week-{month}"] = f"{monthly_price:.2f}" if monthly_price is not None else "N/A"
        
        # Find the company slug and create the link
        company_id = next((id for id, info in company_info.items() if info['name'] == company), None)
        if company_id:
            company_slug = company_info[company_id]['slug']
            payload["fieldData"][f"winner-{i}-link"] = f"/strom/stromleverandorer/{company_slug}"
        else:
            payload["fieldData"][f"winner-{i}-link"] = ""
    
    url = f"{BASE_URL}/collections/{POWER_HERO_COLLECTION_ID}/items/{POWER_HERO_ITEM_ID}"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {webflow_bearer_token}"
    }
    
    try:
        response = requests.patch(url, json=payload, headers=headers)
        response.raise_for_status()
        print("Successfully updated Winner Power Hero")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Failed to update Winner Power Hero. Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Response content:")
            print(e.response.text)

def get_all_power_deals():
    all_deals = []
    offset = 0
    limit = 100
    
    while True:
        url = f"{BASE_URL}/collections/666369a1306b05c2b711042d/items?limit={limit}&offset={offset}"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {webflow_bearer_token}"
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        
        items = data.get('items', [])
        for item in items:
            fields = item.get('fieldData', {})
            deal = {
                'id': item['id'],
                'name': fields.get('name', ''),
                'addonprice': float(fields.get('addonprice', 0)),
                'monthlyfee': float(fields.get('monthlyfee', 0)),
                'feemail': float(fields.get('feeMail', 0))
            }
            all_deals.append(deal)
        
        if len(items) < limit:
            break
        
        offset += limit
    
    return all_deals

def calculate_rankings(all_deals):
    # Calculate total cost for each deal
    for deal in all_deals:
        deal['total_cost'] = deal['addonprice'] + deal['monthlyfee'] + deal['feemail']
    
    # Sort deals by total cost
    sorted_deals = sorted(all_deals, key=lambda x: x['total_cost'])
    
    # Assign rankings
    rankings = {deal['id']: rank + 1 for rank, deal in enumerate(sorted_deals)}
    
    return rankings, len(all_deals), sorted_deals

def get_company_info():
    url = "https://api.webflow.com/v2/collections/667c332ea80584f74f272d0b/items?limit=100"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {webflow_bearer_token}"
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    
    company_info = {}
    for item in data.get('items', []):
        company_info[item['id']] = {
            'name': item['fieldData'].get('name', ''),
            'logo_url': item['fieldData'].get('logo', {}).get('url', ''),
            'slug': item['fieldData'].get('slug', ''),
            'affiliate-link': item['fieldData'].get('affiliate-link', '')
        }
    
    return company_info

def calculate_monthly_cost(average_price, deal_info):
    addon_price = float(deal_info['addonprice'])
    total_price = average_price + addon_price
    monthly_usage = 1333.33  # kWh
    
    cost = total_price * monthly_usage
    if deal_info['monthlyfee']:
        cost += float(deal_info['monthlyfee'])
    
    return cost

def find_best_deals(company_info, average_price, rankings, total_deals):
    best_deal_1 = None
    best_deal_2 = None
    offset = 0
    limit = 100
    
    strompris_data = get_strompris_data()
    
    while True:
        url = f"{BASE_URL}/collections/666369a1306b05c2b711042d/items?limit={limit}&offset={offset}"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {webflow_bearer_token}"
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        
        items = data.get('items', [])
        
        for item in items:
            fields = item.get('fieldData', {})
            if (fields.get('producttype') == 'Timespot' and 
                fields.get('applicabletocustomers') == 'newAndExistingCustomers'):
                
                # Check if the product is available in regionNO1
                product_id = fields.get('slug')
                if not is_product_in_region_no1(product_id, strompris_data):
                    continue
                
                addon_price = float(fields.get('addonpriceore', '0').replace(',', '.'))
                fixed_for = int(fields.get('addonpriceminimumfixedfor', '0'))
                
                company_id = fields.get('leverandor')
                company_data = company_info.get(company_id, {})
                
                deal_info = {
                    'id': item['id'],
                    'feeefakturamandatory': fields.get('feeefakturamandatory'),
                    'feeavtalegiromandatory': fields.get('feeavtalegiromandatory'),
                    'priceupdateddate': fields.get('priceupdateddate'),
                    'paymenttype': fields.get('paymenttype'),
                    'feemailapplied': fields.get('feemailapplied'),
                    'pricefromdate': fields.get('pricefromdate'),
                    'vatincluded': fields.get('vatincluded'),
                    'producttype': fields.get('producttype'),
                    'addonprice': fields.get('addonprice'),
                    'addonpriceore': addon_price,
                    'name': fields.get('name'),
                    'affiliate_link': company_data.get('affiliate-link', ''),
                    'addonpriceminimumfixedforunits': fields.get('addonpriceminimumfixedforunits'),
                    'agreementtime': fields.get('agreementtime'),
                    'monthlyfee': fields.get('monthlyfee'),
                    'elcertificateprice': fields.get('elcertificateprice'),
                    'addonpriceminimumfixedfor': fixed_for,
                    'productname': fields.get('productname'),
                    'applicabletocustomers': fields.get('applicabletocustomers'),
                    'company_name': company_data.get('name', 'Unknown Company'),
                    'company_logo_url': company_data.get('logo_url', ''),
                    'company_slug': company_data.get('slug', ''),
                    'average_pricing': average_price + float(fields.get('addonprice', 0)),
                    'monthly_cost': calculate_monthly_cost(average_price, fields),
                    'rank': rankings.get(item['id'], 'N/A'),
                    'total_deals': total_deals,
                    'feemail': float(fields.get('feeMail', 0))
                }
                
                if fixed_for < 6 and (best_deal_1 is None or addon_price < best_deal_1['addonpriceore']):
                    best_deal_1 = deal_info
                
                if fixed_for >= 6 and (best_deal_2 is None or addon_price < best_deal_2['addonpriceore']):
                    best_deal_2 = deal_info
        
        if len(items) < limit:
            break
        
        offset += limit
    
    print(f"Best deal 1: {best_deal_1}")
    print(f"Best deal 2: {best_deal_2}")
    return best_deal_1, best_deal_2

def is_product_in_region_no1(product_id, strompris_data):
    if not strompris_data:
        return False
    for company in strompris_data:
        for product in company.get('products', []):
            if product.get('productId') == product_id:
                return any(area.get('region') == 'regionNO1' for area in product.get('productArea', []))
    return False

def generate_product_writeup(deal_info):
    current_date = datetime.now().strftime("%d. %B %Y")
    current_date = current_date.replace("January", "januar").replace("February", "februar").replace("March", "mars").replace("April", "april").replace("May", "mai").replace("June", "juni").replace("July", "juli").replace("August", "august").replace("September", "september").replace("October", "oktober").replace("November", "november").replace("December", "desember")
    
    company_link = f'<a href="/strom/stromleverandorer/{deal_info["company_slug"]}">{deal_info["company_name"]}</a>'
    
    writeup = f"{deal_info['name']} fra {company_link} er den beste og billigste spotpris avtalen du kan velge {current_date} som har prisgaranti i {deal_info['addonpriceminimumfixedfor']} måneder. "
    writeup += f"Med prisgaranti betyr det at både påslaget og månedsprisen til {deal_info['company_name']} forblir likt i {deal_info['addonpriceminimumfixedfor']} måneder. "
    writeup += f"Den faste månedsprisen til {deal_info['company_name']} er {deal_info['monthlyfee']} kr og påslaget ligger i dag på {deal_info['addonpriceore']} øre/kWh. "

    if deal_info['agreementtime'] == "0":
        writeup += f"{deal_info['name']} fra {deal_info['company_name']} har heller ingen bindingstid, det betyr at du står fritt til å bytte strømleverandør når du ønsker."
    else:
        writeup += f"{deal_info['name']} fra {deal_info['company_name']} har en bindingstid på {deal_info['agreementtime']} måneder."

    return writeup

def create_or_update_winner(winner_number, deal_info, writeup, average_price):
    # Check if the item already exists
    url = f"{BASE_URL}/collections/{COLLECTION_ID}/items"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {webflow_bearer_token}"
    }
    response = requests.get(url, headers=headers)
    items = response.json().get('items', [])
    
    existing_item = next((item for item in items if item['fieldData'].get('name') == f"Winner {winner_number}"), None)
    
    h1_text = f"Beste {deal_info['producttype']} strømavtale med prisgaranti {'under' if deal_info['addonpriceminimumfixedfor'] < 6 else 'over'} 6 måneder"
    
    # Format the monthly price without decimals
    monthly_price_no_decimals = int(round(deal_info['monthly_cost']))
    
    # Determine if it's a short-term or long-term campaign
    campaign_type = "kortvarig" if deal_info['addonpriceminimumfixedfor'] < 6 else "langvarig"
    
    # Get the current month in Norwegian
    current_month = datetime.now().strftime("%B")
    norwegian_months = {
        "January": "januar", "February": "februar", "March": "mars",
        "April": "april", "May": "mai", "June": "juni",
        "July": "juli", "August": "august", "September": "september",
        "October": "oktober", "November": "november", "December": "desember"
    }
    current_month_norwegian = norwegian_months.get(current_month, current_month)
    
    # Format the pricetext
    pricetext = f"Til en månedspris av {monthly_price_no_decimals} kr/mnd har {deal_info['company_name']} den beste og billigste {campaign_type} priskampanje i {current_month_norwegian}"
    
    # Format the ranking text
    ranking_text = f"Av alle {deal_info['total_deals']} strømavtaler i {current_month_norwegian} er også {deal_info['name']} fra {deal_info['company_name']} rangert på {deal_info['rank']}. plass av {deal_info['total_deals']} strømavtaler i Norge basert på den totale kostnaden når vi inkluderer månedsprisen til {deal_info['company_name']} som er på {deal_info['monthlyfee']} kr/mnd, påslaget på {deal_info['addonprice']} kr/kWh og fakturagebyret på {deal_info['feemail']} kr."

    # Format the company link
    company_link = f"/strom/stromleverandorer/{deal_info['company_slug']}"

    payload = {
        "isArchived": False,
        "isDraft": False,
        "fieldData": {
            "name": f"Winner {winner_number}",
            "slug": f"winner-{winner_number}",
            "h1": h1_text,
            "h2": f"Fornye har funnet den beste og billigste strømavtalen du kan bytte til",
            "recommended-deal-1": deal_info['id'],
            "recommended-deal-1-info": f"<p>{writeup}</p>",
            "logo": {
                "url": deal_info['company_logo_url']
            },
            "average-pricing": f"{deal_info['average_pricing']:.5f}",
            "monthlycost": f"{deal_info['monthly_cost']:.2f}",
            "kwhpricenow": f"{average_price:.5f}",
            "pricetext": pricetext,
            "ranking": ranking_text,
            "produktnavn": deal_info['name'],
            "produktpris": f"{monthly_price_no_decimals} kr/mnd",
            "companylink": company_link,
            "affiliate": deal_info.get('affiliate_link', ''),
            "addonore": str(deal_info['addonpriceore']),  # Convert to string
            "fakturagebyr": str(deal_info['feemail']),  # Convert to string
            "prisgaranti": str(deal_info['addonpriceminimumfixedfor'])  # Convert to string
        }
    }

    # Remove the 'affiliate' field if it's empty
    if not payload['fieldData']['affiliate']:
        del payload['fieldData']['affiliate']
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {webflow_bearer_token}"
    }
    
    if existing_item:
        # Update existing item
        url = f"{BASE_URL}/collections/{COLLECTION_ID}/items/{existing_item['id']}"
        response = requests.patch(url, json=payload, headers=headers)
    else:
        # Create new item
        url = f"{BASE_URL}/collections/{COLLECTION_ID}/items"
        response = requests.post(url, json=payload, headers=headers)
    
    response.raise_for_status()
    print(f"Successfully {'updated' if existing_item else 'created'} Winner {winner_number}")
    print("Response:")
    print(json.dumps(response.json(), indent=2))

def update_best_power_deals():
    average_price = get_average_electricity_price()
    all_deals = get_all_power_deals()
    rankings, total_deals, sorted_deals = calculate_rankings(all_deals)
    company_info = get_company_info()
    best_deal_1, best_deal_2 = find_best_deals(company_info, average_price, rankings, total_deals)

    writeup_1 = generate_product_writeup(best_deal_1)
    writeup_2 = generate_product_writeup(best_deal_2)

    create_or_update_winner(1, best_deal_1, writeup_1, average_price)
    create_or_update_winner(2, best_deal_2, writeup_2, average_price)
    
    # Get the top 5 cheapest companies and weekly prices
    top_5_cheapest, monthly_prices = get_cheapest_companies()
    
    # Update the Winner Power Hero item
    update_winner_power_hero(total_deals, sorted_deals, top_5_cheapest, monthly_prices)

if __name__ == "__main__":
    update_best_power_deals()