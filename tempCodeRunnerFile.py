from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User  # Import db and User from models.py
from bs4 import BeautifulSoup
import requests
import random
from urllib.parse import quote
from dotenv import load_dotenv
import os
import time
import csv
from data import getStaticGigs
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY')
db.init_app(app)

@app.route('/')
def index():
    return render_template('index.html')

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

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

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

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html')
    return redirect(url_for('login'))

@app.route('/search', methods=['GET'])
def search():
    if 'username' not in session:
        return redirect(url_for('login'))

    keywords = request.args.get('keywords', '').strip().replace(' ', '%20')
    seller_types = request.args.getlist('seller_types')  # Optional field
    seller_countries = request.args.getlist('seller_countries')  # Optional field

    if not keywords:
        flash("Keywords are required", "danger")
        return redirect(url_for('dashboard'))

    results = scrape_fiverr(keywords, seller_types, seller_countries)
    return render_template('search.html', results=results)

def delete_existing_files():
    if os.path.exists('scraped_gigs.csv'):
        os.remove('scraped_gigs.csv')

def save_to_csv(gigs):
    delete_existing_files()
    
    file_path = 'scraped_gigs.csv'
    headers = ['Title', 'Description', 'Sales', 'Rating', 'Price', 'Industry', 'Platform', 'Last Delivery', 'Seller Rank', 'Member Since']
    
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        
        for gig in gigs:
            writer.writerow({
                'Title': gig['title'],
                'Description': gig['description'],
                'Sales': gig['sales'],
                'Rating': gig['rating'],
                'Price': gig['price'],
                'Industry': gig['industry'],
                'Platform': gig['platform'],
                'Last Delivery': gig['last_delivery'],
                'Seller Rank': gig['seller_rank'],
                'Member Since': gig['member_since'],
            })

    print(f"Data saved to {file_path}")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Windows; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8",
    "Mozilla/5.0 (Windows NT 10.0; Windows; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Windows; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36"
]

def setup_selenium_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.headless = False  # Set to False for visible browser window
    service = Service(executable_path='C:/chromedriver/chromedriver.exe')  # Update path to chromedriver
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def smooth_scroll(driver):
    last_position = driver.execute_script("return window.pageYOffset;")
    while True:
        driver.execute_script("window.scrollBy(0, 100);")
        time.sleep(2)
        new_position = driver.execute_script("return window.pageYOffset;")
        if new_position == last_position:
            break
        last_position = new_position

    scroll_height = driver.execute_script("return document.body.scrollHeight;")
    if last_position >= scroll_height:
        return

def scrape_fiverr(keywords, seller_types=None, seller_countries=None, gigs_count=15):
    base_url = 'https://www.fiverr.com/search/gigs'
    all_gigs = []
    gigs_fetched = 0

    ref_value = ''
    if seller_types:
        ref_value += 'seller_level:' + '|'.join(seller_types)
    if seller_countries:
        if ref_value:
            ref_value += '|'
        ref_value += 'seller_location:' + '|'.join(seller_countries)

    query_params = {
        'query': keywords,
        'source': 'drop_down_filters',
        'ref': quote(ref_value),
        'page': 1
    }

    url = base_url + '?' + '&'.join([f'{key}={value}' for key, value in query_params.items()])
    print(f'Hitting URL for first page: {url}')

    try:
        driver = setup_selenium_driver()
        driver.get(url)
        smooth_scroll(driver)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        gigs = []

        for gig in soup.find_all('div', class_='gig-wrapper-impressions'):
            if gigs_fetched >= gigs_count:
                break

            title = gig.find('p', {'role': 'heading'}).text.strip() if gig.find('p', {'role': 'heading'}) else 'N/A'
            seller_rank = gig.find('p', class_='z58z872').text.strip() if gig.find('p', class_='z58z872') else 'N/A'
            rating = gig.find('strong', class_='rating-score').text.strip() if gig.find('strong', class_='rating-score') else 'N/A'
            price = gig.find('span', class_='co-grey-1200').text.strip() if gig.find('span', class_='co-grey-1200') else 'N/A'
            relative_gig_url = gig.find('a', class_='relative')
            gig_url = 'https://www.fiverr.com' + relative_gig_url['href'] if relative_gig_url else None

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
                'rating': rating,
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
        time.sleep(random.uniform(5, 15))

        driver.quit()

    except Exception as e:
        print(f"Error during scraping: {e}")

    save_to_csv(all_gigs)
    return all_gigs

def scrape_gig_details(gig_url):
    try:
        response = requests.get(gig_url, headers={'User-Agent': random.choice(USER_AGENTS)})
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract details here with default fallback
    sales_count_text = soup.find('span', class_='rating-count-number')
    sales_count = int(sales_count_text.get_text(strip=True).replace(',', '')) if sales_count_text else 0

    user_stats = soup.select_one('ul.user-stats')
    member_since_year = 'N/A'
    if user_stats:
        member_since_text = user_stats.select_one('li:nth-child(2) strong').get_text(strip=True)
        if member_since_text:
            member_since_year = member_since_text.split()[-1]

    return {
        'description': soup.find('div', class_='description-content').get_text(separator='\n').strip() if soup.find('div', class_='description-content') else 'N/A',
        'sales_count': sales_count,
        'industry': soup.select_one('nav ol.zle7n00 li:nth-child(3) a').get_text(strip=True) if soup.select_one('nav ol.zle7n00 li:nth-child(3) a') else 'N/A',
        'platform': soup.select_one('nav ol.zle7n00 li:nth-child(4) a').get_text(strip=True) if soup.select_one('nav ol.zle7n00 li:nth-child(4) a') else 'N/A',
        'last_delivery': soup.find('span', class_='last-delivery').get_text(strip=True) if soup.find('span', class_='last-delivery') else 'N/A',
        'member_since': member_since_year
    }

@app.route('/run-nlp-regression', methods=['POST'])
def run_nlp_regression_route():
    # This will run the external script to open the GUI
    subprocess.Popen(['python', 'run_analysis.py'])
    return "NLP Regression GUI launched!", 200

if __name__ == '__main__':
    app.run(debug=True) 