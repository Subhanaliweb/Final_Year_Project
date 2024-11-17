def wait_for_elements(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.gig-page'))
        )
    except TimeoutException:
        print("Timed out waiting for elements")


def scrape_fiverr(final_url, gigs_count=40):
    all_gigs = []
    gigs_fetched = 0

    print(f'Hitting URL: {final_url}')

    driver = setup_selenium_driver()
    try:
        driver.get(final_url)
        time.sleep(5)
        smooth_scroll(driver)

        wait_for_elements(driver)  # Wait for the gig URLs to appear
        
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
            if relative_gig_url:
                gig_url = f"https://www.fiverr.com{relative_gig_url['href']}"
            else:
                gig_url = None

            gig_details = {}
            attempts = 0
            while attempts < 3:
                if gig_url:
                    time.sleep(2)
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
