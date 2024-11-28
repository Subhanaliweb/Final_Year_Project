import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from textblob import TextBlob
import matplotlib.pyplot as plt
import plotly.express as px
import seaborn as sns
import time
import sys

def run_analysis(file_path):
    # Load data
    data = pd.read_csv(file_path)

    # NLP Analysis: Keyword extraction from Title and Description
    vectorizer_title = CountVectorizer(stop_words='english', max_features=20)
    vectorizer_desc = CountVectorizer(stop_words='english', max_features=20)

    # Transform 'Title' and 'Description' columns to get focus keywords
    title_keywords_matrix = vectorizer_title.fit_transform(data['Title'].fillna(""))
    desc_keywords_matrix = vectorizer_desc.fit_transform(data['Description'].fillna(""))

    # Mapping keywords to their frequency counts
    title_keywords_freq = title_keywords_matrix.sum(axis=0).A1
    desc_keywords_freq = desc_keywords_matrix.sum(axis=0).A1
    title_keywords = dict(zip(vectorizer_title.get_feature_names_out(), title_keywords_freq))
    desc_keywords = dict(zip(vectorizer_desc.get_feature_names_out(), desc_keywords_freq))

    # Sentiment Analysis for Title and Description
    data['Title_Sentiment'] = data['Title'].apply(lambda x: TextBlob(str(x)).sentiment.polarity)
    data['Description_Sentiment'] = data['Description'].fillna("").apply(lambda x: TextBlob(str(x)).sentiment.polarity)

    # Count keywords for each row to analyze correlation with Sales
    data['Title_Keyword_Count'] = title_keywords_matrix.sum(axis=1).A1
    data['Desc_Keyword_Count'] = desc_keywords_matrix.sum(axis=1).A1

    # Convert 'Last Delivery' to numeric days for time analysis
    data['Last Delivery (days)'] = pd.to_numeric(data['Last Delivery'], errors='coerce')

    # Correlation analysis between Sales, Rating, Price, and keyword counts
    correlation_matrix = data[['Sales', 'Rating', 'Price', 'Title_Keyword_Count', 
                                'Desc_Keyword_Count', 'Last Delivery (days)']].corr()

    # --- 1. Bar Chart for Top Keywords in Titles ---
    plt.figure(figsize=(10, 6))
    plt.bar(title_keywords.keys(), title_keywords.values(), color='skyblue')
    plt.title('Top Keywords in Titles')
    plt.xlabel('Keywords')
    plt.ylabel('Frequency')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    # --- 2. Bar Chart for Top Keywords in Descriptions ---
    plt.figure(figsize=(10, 6))
    plt.bar(desc_keywords.keys(), desc_keywords.values(), color='salmon')
    plt.title('Top Keywords in Descriptions')
    plt.xlabel('Keywords')
    plt.ylabel('Frequency')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    # --- 3. Correlation Heatmap ---
    plt.figure(figsize=(8, 6))
    sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt=".2f")
    plt.title('Correlation Matrix')
    plt.show()
    time.sleep(2)

    # --- 4. Sales Distribution by Title Keyword Count ---
    fig = px.scatter(data, x='Title_Keyword_Count', y='Sales', color='Rating',
                     title="Sales by Title Keyword Count",
                     labels={'Title_Keyword_Count': 'Keyword Count in Title', 'Sales': 'Total Sales'})
    time.sleep(2)
    fig.show()

    # --- 5. Sales Distribution by Description Keyword Count ---
    fig = px.scatter(data, x='Desc_Keyword_Count', y='Sales', color='Price',
                     title="Sales by Description Keyword Count",
                     labels={'Desc_Keyword_Count': 'Keyword Count in Description', 'Sales': 'Total Sales'})
    time.sleep(2)
    fig.show()

    # --- 6. Sales vs. Delivery Time Scatter Plot ---
    fig = px.scatter(data, x='Last Delivery (days)', y='Sales', color='Rating',
                     title="Sales by Delivery Time",
                     labels={'Last Delivery (days)': 'Delivery Time (days)', 'Sales': 'Total Sales'})
    time.sleep(2)
    fig.show()

    # --- 7. Keyword-Sales Contribution Analysis ---
    top_keywords_sales = data[['Title', 'Sales']].copy()
    top_keywords_sales['Top Keyword'] = top_keywords_sales['Title'].apply(
        lambda x: max(vectorizer_title.get_feature_names_out(), key=lambda kw: x.lower().count(kw), default="None")
    )
    keyword_sales_summary = top_keywords_sales.groupby('Top Keyword')['Sales'].sum().sort_values(ascending=False)

    plt.figure(figsize=(10, 6))
    keyword_sales_summary[:10].plot(kind='bar', color='lightgreen')
    plt.title('Top Keywords by Sales Contribution')
    plt.xlabel('Keyword')
    plt.ylabel('Total Sales')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Error: Missing file path argument.")
        sys.exit(1)
    # Get file path from command line arguments
    file_path = sys.argv[1]
    run_analysis(file_path)
