from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User 
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
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
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['username'] = username
            return redirect(url_for('dashboard'))
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
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already registered', 'danger')
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Successfully registered! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

# DASHBOARD ROUTE
@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html')
    return redirect(url_for('login'))

# SEARCH ROUTE
@app.route('/search', methods=['GET'])
def search():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Get finalUrl directly from the request arguments
    final_url = request.args.get('finalUrl')
    print(f"final_url received: {final_url}")   
    
    if not final_url:
        flash("finalUrl is required", "danger")
        return redirect(url_for('dashboard'))

    # Pass finalUrl directly to the scrape function
    results = scrape_fiverr(final_url)

    return render_template('search.html', results=results)

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



def scrape_fiverr(final_url, gigs_count=10):
    all_gigs = []
    gigs_fetched = 0

    print(f'Hitting URL: {final_url}')

    driver = setup_selenium_driver()
    try:
        driver.get(final_url)
        time.sleep(3)
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
            
            # If Fiverr's Choice badge is found, skip the gig
            if fiverr_choice_badge:
                continue  # Skip this gig if it's "Fiverr's Choice"

            title = gig.find('p', {'role': 'heading'}).text.strip() if gig.find('p', {'role': 'heading'}) else None
            seller_rank = gig.find('p', class_='z58z872').text.strip() if gig.find('p', class_='z58z872') else None
            price = gig.find('span', class_='co-grey-1200').text.strip() if gig.find('span', class_='co-grey-1200') else None

            # Clean the price by removing commas and non-numeric characters
            if price != None:
                price = re.sub(r'[^\d]', '', price)  # Remove all non-digit characters
                
            relative_gig_url = gig.select_one('a.relative')
            gig_url = f"https://www.fiverr.com{relative_gig_url['href']}" if relative_gig_url else None

            gig_details = {}
            attempts = 0
            while attempts < 3:
                if gig_url:
                    gig_details = scrape_gig_details(gig_url)
                    if gig_details:  # Check if data was successfully fetched
                        break
                attempts += 1
                time.sleep(2)  # Optional wait between retries
        
            gigs.append({
                'title': title,
                'description': gig_details.get('description', 'N/A'),
                'sales': gig_details.get('sales_count', 'N/A'),
                'rating': gig_details.get('rating', 'N/A'),
                'price': price,
                'industry': gig_details.get('industry', 'N/A'),
                'platform': gig_details.get('platform', 'N/A'),
                'last_delivery': gig_details.get('last_delivery', 'N/A'),
                'seller_rank': seller_rank,
                'member_since': gig_details.get('member_since', 'N/A')
            })
            gigs_fetched += 1
            time.sleep(1)

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

@app.route('/run-nlp-regression', methods=['POST'])
def run_nlp_regression_route():
    # This will run the external script to open the GUI
    subprocess.Popen(['python', 'run_analysis.py'])
    return "NLP Regression GUI launched!", 200

if __name__ == '__main__':
    app.run(debug=True) 