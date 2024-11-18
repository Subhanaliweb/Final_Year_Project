from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User 
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from fake_useragent import UserAgent
from dotenv import load_dotenv
import requests
import random
import os
import time
import csv
import subprocess
import re
from urllib.parse import urlparse, parse_qs

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY')
db.init_app(app)

# Configure headers with a rotating user agent
def get_headers():
    return {"User-Agent": UserAgent().random}

# HOME ROUTE
@app.route('/')
def index():
    return render_template('index.html')

# LOGIN ROUTE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('search'))

    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['username'] = username
            return redirect(url_for('search'))
        flash('Invalid username or password', 'danger')

    return render_template('login.html')

# ANALYSIS ROUTE
@app.route('/analysis')
def analysis():
    if 'username' in session:
        return render_template('analysis.html')
    return redirect(url_for('login'))

# LOGOUT ROUTE
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

# REGISTER ROUTE
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('search'))

    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already registered', 'danger')
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Successfully registered!', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

# search ROUTE
@app.route('/search')
def search():
    if 'username' in session:
        return render_template('search.html')
    return redirect(url_for('login'))

# SEARCH RESTULS ROUTE
@app.route('/search-results', methods=['GET'])
def search_results():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Get finalUrl directly from the request arguments
    final_url = request.args.get('finalUrl')
    print(f"final_url received: {final_url}")   
    
    if not final_url:
        flash("finalUrl is required", "danger")
        return redirect(url_for('search'))

    # Pass finalUrl directly to the scrape function
    results = scrape_fiverr(final_url)

    return render_template('search-results.html', results=results)

# FUNCTION TO DELTE EXISITNG CSV
def delete_existing_files():
    if os.path.exists('scraped_gigs.csv'):
        os.remove('scraped_gigs.csv')

def convert_last_delivery_to_hours(last_delivery):
    """
    Converts 'last delivery' data into hours.
    Example:
    - 'about 9 hours' -> 9
    - '1 week' -> 168 (7 days * 24 hours)
    - '4 days' -> 96 (4 * 24 hours)
    - 'about 57 minutes' -> 1 (rounded up)
    - 'just now' -> 0 (considered as 0 hours)
    """
    if not last_delivery or last_delivery.lower() == 'n/a':
        return None  # Handle missing or invalid data gracefully

    # Handle 'just now' or 'Just Now' case
    if 'just now' in last_delivery.lower():
        return 0  # Treat 'just now' as 0 hours
    
    # Regular expressions for matching time units (support both singular and plural)
    weeks = re.search(r"(\d+)\s*week[s]?", last_delivery, re.IGNORECASE)
    days = re.search(r"(\d+)\s*day[s]?", last_delivery, re.IGNORECASE)
    hours = re.search(r"(\d+)\s*hour[s]?", last_delivery, re.IGNORECASE)
    minutes = re.search(r"(\d+)\s*minute[s]?", last_delivery, re.IGNORECASE)

    total_hours = 0

    if weeks:
        total_hours += int(weeks.group(1)) * 7 * 24
    if days:
        total_hours += int(days.group(1)) * 24
    if hours:
        total_hours += int(hours.group(1))
    if minutes:
        total_hours += 1  # Round up minutes to 1 hour

    return total_hours

# FUNCTION TO CREATE CSV
def save_to_csv(gigs):
    delete_existing_files()
    
    file_path = 'scraped_gigs.csv'
    headers = ['Title', 'Description', 'Sales', 'Rating', 'Price', 'Industry', 'Platform', 
               'Last Delivery', 'Seller Rank', 'Member Since']
    
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        
        for gig in gigs:
            last_delivery_hours = convert_last_delivery_to_hours(gig['last_delivery'])
            writer.writerow({
                'Title': gig['title'],
                'Description': gig['description'],
                'Sales': gig['sales'],
                'Rating': gig['rating'],
                'Price': gig['price'],
                'Industry': gig['industry'],
                'Platform': gig['platform'],
                'Last Delivery': last_delivery_hours,
                'Seller Rank': gig['seller_rank'],
                'Member Since': gig['member_since'],
            })

    print(f"Data saved to {file_path}")




def setup_selenium_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")  # Disable GPU rendering
    options.add_argument("--ignore-certificate-errors")  # Ignore SSL errors
    options.headless = False   # Set to False for visible browser window
    service = Service(executable_path='C:/chromedriver/chromedriver.exe')  # Update path to chromedriver
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def smooth_scroll(driver):
    last_position = driver.execute_script("return window.pageYOffset;")
    while True:
        driver.execute_script("window.scrollBy(0, 250);")
        time.sleep(2)
        new_position = driver.execute_script("return window.pageYOffset;")
        if new_position == last_position:
            break
        last_position = new_position

    scroll_height = driver.execute_script("return document.body.scrollHeight;")
    if last_position >= scroll_height:
        return

def scrape_fiverr(final_url, gigs_count=20):
    all_gigs = []
    gigs_fetched = 0

    print(f'Hitting URL: {final_url}')

    driver = setup_selenium_driver()
    try:
        driver.get(final_url)
        time.sleep(5)
        smooth_scroll(driver)

        
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        gigs = []

        for gig in soup.find_all('div', class_='gig-wrapper-impressions'):
            if gigs_fetched >= gigs_count:
                break

            skip_classes = {'pro-experience', 'agency-card-v2'}
            if any(cls in skip_classes for cls in gig.get('class', [])):
                continue

            # Check if the gig has the "Fiverr's Choice" badge
            fiverr_choice_badge = gig.find('div', class_='z58z870 z58z87103 z58z871b7')
            if fiverr_choice_badge:
                continue  # Skip this gig if it's "Fiverr's Choice"

            title = gig.find('p', {'role': 'heading'}).text.strip() if gig.find('p', {'role': 'heading'}) else None
            seller_rank = gig.find('p', class_='z58z872').text.strip() if gig.find('p', class_='z58z872') else "New Seller"
            price = gig.find('span', class_='co-grey-1200').text.strip() if gig.find('span', class_='co-grey-1200') else None

            # Clean the price by removing commas and non-numeric characters
            if price:
                price = re.sub(r'[^\d]', '', price)  # Remove all non-digit characters

            relative_gig_url = gig.select_one('a.relative')
            gig_url = f"https://www.fiverr.com{relative_gig_url['href']}" if relative_gig_url else None

            gig_details = {}
            attempts = 0
            while attempts < 3:
                if gig_url:
                    time.sleep(3)
                    gig_details = scrape_gig_details(gig_url)
                    if gig_details:  # Check if data was successfully fetched
                        break
                attempts += 1
                time.sleep(3)  # Optional wait between retries

            # Initialize gig_data dictionary
            gig_data = {
                'title': title,
                'description': gig_details.get('description', None),
                'sales': gig_details.get('sales_count', None),
                'rating': gig_details.get('rating', None),
                'price': price,
                'industry': gig_details.get('industry', None),
                'platform': gig_details.get('platform', None),
                'last_delivery': gig_details.get('last_delivery', None),
                'seller_rank': seller_rank,
                'member_since': gig_details.get('member_since', None)
            }

            # Check if any required field is missing, empty, or has "N/A"
            required_fields = [
                'title', 'description', 'sales', 'rating', 'price',
                'industry', 'platform', 'last_delivery', 'seller_rank', 'member_since'
            ]
            # Log missing fields for skipped gigs
            missing_fields = [field for field in required_fields if gig_data.get(field) in [None, '', 'N/A']]
            if missing_fields:
                print(f"Skipping gig due to missing fields: {missing_fields}")
                continue  # Skip this gig if any field is missing, empty, or "N/A"

            gigs.append(gig_data)
            gigs_fetched += 1
            time.sleep(2)

        all_gigs.extend(gigs)
        time.sleep(random.uniform(2, 4))

        driver.quit()

    except Exception as e:
        print(f"Error during scraping: {e}")

    save_to_csv(all_gigs)
    return all_gigs

def parse_sales_count(sales_text):
    """
    Parses sales count strings like '2.5k' or '1.5M' to integers.
    'k' means thousands, 'M' means millions.
    """
    if 'k' in sales_text.lower():
        return int(float(sales_text.replace('k', '').replace('K', '').strip()) * 1000)
    elif 'm' in sales_text.lower():
        return int(float(sales_text.replace('m', '').replace('M', '').strip()) * 1000000)
    else:
        return int(sales_text.strip().replace(',', ''))  # Clean commas and convert

def scrape_gig_details(gig_url):
    try:
        response = requests.get(gig_url, headers=get_headers())
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract sales count with the helper function
    sales_count_text = soup.find('span', class_='rating-count-number')
    if not sales_count_text:
        sales_count_text = soup.select_one('.seller-card button span.zle7n0d')

    sales_count = parse_sales_count(sales_count_text.get_text(strip=True).replace(',', '')) if sales_count_text else 0

    user_stats = soup.select_one('ul.user-stats')
    member_since_year = 'N/A'
    if user_stats:
        member_since_text = user_stats.select_one('li:nth-child(2) strong').get_text(strip=True)
        if member_since_text:
            member_since_year = member_since_text.split()[-1]

    return {
        'description': soup.find('div', class_='description-content').get_text(separator='\n').strip() if soup.find('div', class_='description-content') else 'N/A',
        'sales_count': sales_count,
        'rating' : soup.find('strong', class_='rating-score').text.strip() if soup.find('strong', class_='rating-score') else 'N/A',
        'industry': soup.select_one('nav ol.zle7n00 li:nth-child(3) a').get_text(strip=True) if soup.select_one('nav ol.zle7n00 li:nth-child(3) a') else 'N/A',
        'platform': soup.select_one('nav ol.zle7n00 li:last-child a').get_text(strip=True) if soup.select_one('nav ol.zle7n00 li:last-child a') else 'N/A',
        'last_delivery': soup.select_one('.user-stats li:nth-child(4) strong').get_text(strip=True) if soup.select_one('.user-stats li:nth-child(4) strong') else 'N/A',
        'member_since': member_since_year
    }


# Flask route to receive filter data
@app.route('/custom-filters', methods=['POST'])
def custom_filters():
    if request.is_json:
        filter_data = request.get_json()
        listings_started = filter_data.get('listings_started')
        min_sales = filter_data.get('sales_count')
        min_rating = filter_data.get('rating')
        
        # Convert filters as needed
        start_year = int(listings_started) if listings_started else None
        min_sales = int(min_sales) if min_sales else None
        min_rating = float(min_rating) if min_rating else None

        # Apply filters and generate filtered CSV
        apply_filters_and_save(start_year=start_year, min_sales=min_sales, min_rating=min_rating)

        return jsonify({"message": "Filters applied successfully, filtered CSV generated!"}), 200
    else:
        return jsonify({"error": "Invalid request format"}), 400


# Function to filter data and save to a new CSV
def apply_filters_and_save(start_year=None, min_rating=None, min_sales=None):
    input_file = 'scraped_gigs.csv'
    output_file = 'filtered_gigs.csv'

    try:
        with open(input_file, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            filtered_gigs = []
            
            for row in reader:
                # Filter by start year
                if start_year and int(row['Member Since']) < start_year:
                    continue
                
                # Filter by minimum rating
                if min_rating and float(row['Rating']) < min_rating:
                    continue
                
                # Filter by maximum price
                if min_sales and float(row['Sales']) < min_sales:
                    continue
                
                # Add row if all conditions pass
                filtered_gigs.append(row)
        
        # Save filtered data to a new CSV file
        with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(filtered_gigs)
        
        print(f"Filtered data saved to {output_file}")
    except Exception as e:
        print(f"Error during filtering: {e}")


@app.route('/run-nlp-regression', methods=['POST'])
def run_nlp_regression_route():
    try:
        # Extract file path from request JSON
        data = request.get_json()
        file_path = data.get('file_path')

        if not file_path:
            return jsonify({"message": "File path is required!"}), 400

        # Pass file path as an argument to the subprocess
        subprocess.Popen(['python', 'run_analysis.py', file_path])

        return jsonify({"message": "Analysis GUI launching..."}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to launch Analysis GUI: {str(e)}"}), 500

# Route for filtered results (you can define the logic for filtered data)
@app.route('/view-filtered-results', methods=['POST'])
def view_filtered_results():
    try:
        # Extract file path from request JSON
        data = request.get_json()
        file_path = data.get('file_path')

        if not file_path:
            return jsonify({"message": "File path is required!"}), 400

        # Pass file path as an argument to the subprocess
        subprocess.Popen(['python', 'run_analysis.py', file_path])

        return jsonify({"message": "Filtered Analysis GUI launching..."}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to load filtered analysis: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True) 