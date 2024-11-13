from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User  # Import db and User from models.py
from bs4 import BeautifulSoup
import requests
import random
from urllib.parse import quote
from dotenv import load_dotenv
import os
import time # DON'T DELETE THIS
import csv
from data import getStaticGigs
import subprocess


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
    print(keywords)
    seller_types = request.args.getlist('seller_types')  # Optional field
    seller_countries = request.args.getlist('seller_countries')  # Optional field
    # gigs_count = int(request.args.get('gigs_count'))  # Default to 10 if not specified

    if not keywords:
        flash("Keywords are required", "danger")
        return redirect(url_for('dashboard'))

    # nlp_regression.run_analysis()
    # Pass empty lists if seller_types or seller_countries are not provided
    results = scrape_fiverr(keywords, seller_types, seller_countries)
    return render_template('search.html', results=results)

def delete_existing_files():
    # Check if the files exist and delete them
    if os.path.exists('scraped_gigs.csv'):
        os.remove('scraped_gigs.csv')
    if os.path.exists('gigs_analysis.html'):
        os.remove('gigs_analysis.html')

def save_to_csv(gigs):
    # Delete old files
    delete_existing_files()
    
    # Define the CSV file path
    file_path = 'scraped_gigs.csv'
    
    # Define the column headers
    headers = ['Title', 'Description', 'Sales', 'Rating', 'Price', 'Industry', 'Platform', 'Last Delivery', 'Seller Rank', 'Member Since']
    
    # Write data to CSV
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        
        # Write header
        writer.writeheader()
        
        # Write each gig's data
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
    # 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    # 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    # 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',


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

def scrape_fiverr(keywords, seller_types=None, seller_countries=None, gigs_count=30):
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
        'page': 1  # Only fetch the first page
    }

    url = base_url + '?' + '&'.join([f'{key}={value}' for key, value in query_params.items()])
    print(f'Hitting URL for first page: {url}')
    headers = {'User-Agent': random.choice(USER_AGENTS), 'Accept-Language': 'en-US,en;q=0.9'}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        if response.status_code == 403:
            print(f"Blocked while fetching the first page. Stopping scrape.")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
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
            gig_details = scrape_gig_details(gig_url) if gig_url else {}

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

            # Add a 1-second delay between each gig scrape
            time.sleep(1)

        all_gigs.extend(gigs)
        time.sleep(random.uniform(5, 15))

    except requests.exceptions.RequestException as e:
        print(f"Error during request to Fiverr: {e}")

    save_to_csv(all_gigs)
    return all_gigs

def scrape_gig_details(gig_url):
    try:
        response = requests.get(gig_url, headers={'User-Agent': random.choice(USER_AGENTS)})
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')

    # Parse and convert sales count
    sales_count_text = soup.find('span', class_='rating-count-number')
    if sales_count_text:
        try:
            # Extract digits only and convert to int or float
            sales_count = int(sales_count_text.get_text(strip=True).replace(',', ''))
        except ValueError:
            sales_count = 0  # Or 'N/A' if that's preferred
    else:
        sales_count = 0  # Or 'N/A'


    user_stats = soup.select_one('ul.user-stats')
    
    # Check if user_stats is found before trying to access it
    if user_stats:
        member_since_text = user_stats.select_one('li:nth-child(2) strong').get_text(strip=True)

        # Default value if not found
        member_since_year = 'N/A'

        # Extract year from the "Member since" text (assuming format "Month Year")
        if member_since_text:
            # Split the text and extract the year (assuming the format is "Month Year")
            member_since_year = member_since_text.split()[-1]  # Take the last part, which should be the year
    else:
        member_since_year = 'N/A'  # Default value if user_stats is not found

    print(f"Member since year: {member_since_year}")
    
    return {
        'industry': soup.select_one('nav ol.zle7n00 li:nth-child(3) a').get_text(strip=True) if soup.select_one('nav ol.zle7n00 li:nth-child(3) a') else 'N/A',
        'platform': soup.select_one('nav ol.zle7n00 li:nth-child(7) a').get_text(strip=True) if soup.select_one('nav ol.zle7n00 li:nth-child(7) a') else 'N/A',
        'last_delivery': soup.select_one('.user-stats li:nth-child(4) strong').get_text(strip=True) if soup.select_one('.user-stats li:nth-child(4) strong') else 'N/A',
        'description': soup.find('div', class_='description-content').get_text(separator='\n').strip() if soup.find('div', class_='description-content') else 'N/A',
        'sales_count': sales_count,  
        'member_since': member_since_year
    }

@app.route('/run-nlp-regression', methods=['POST'])
def run_nlp_regression_route():
    # This will run the external script to open the GUI
    subprocess.Popen(['python', 'run_analysis.py'])
    return "NLP Regression GUI launched!", 200

if __name__ == '__main__':
    app.run(debug=True) 