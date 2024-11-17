import pandas as pd
import re
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from textblob import TextBlob
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import time

def run_analysis():
    # Load data
    file_path = 'scraped_gigs.csv'  # Change to your file path
    data = pd.read_csv(file_path)

    # Clean Price column by removing non-numeric characters
    data['Price'] = data['Price'].apply(lambda x: re.sub(r'[^0-9]', '', str(x))).astype(float)

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

    # Regression Analysis (Optional)
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_squared_error, r2_score

    # Define features and target variable for regression
    X = data[['Rating', 'Price', 'Title_Keyword_Count', 'Desc_Keyword_Count']]
    y = data['Sales']

    # Split data into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    # Initialize and train regression model
    model = LinearRegression()
    model.fit(X_train, y_train)

    # Make predictions and evaluate
    y_pred = model.predict(X_test)

    # --- 1. Bar Chart for Top Keywords in Titles and Descriptions ---
    # Title Keywords Bar Chart
    plt.figure(figsize=(10, 6))
    plt.bar(title_keywords.keys(), title_keywords.values(), color='skyblue')
    plt.title('Top Keywords in Titles')
    plt.xlabel('Keywords')
    plt.ylabel('Frequency')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    # Description Keywords Bar Chart
    plt.figure(figsize=(10, 6))
    plt.bar(desc_keywords.keys(), desc_keywords.values(), color='salmon')
    plt.title('Top Keywords in Descriptions')
    plt.xlabel('Keywords')
    plt.ylabel('Frequency')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    # --- 2. Correlation Heatmap ---
    plt.figure(figsize=(8, 6))
    sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt=".2f")
    plt.title('Correlation Matrix')
    plt.show()
    time.sleep(2)

    # --- 3. Regression Results Scatter Plot ---
    # Scatter plot for actual vs predicted Sales
    y_pred_series = pd.Series(y_pred, index=y_test.index)

    fig = px.scatter(x=y_test, y=y_pred_series, labels={'x': 'Actual Sales', 'y': 'Predicted Sales'},
                    title='Actual vs Predicted Sales')
    fig.add_trace(go.Scatter(x=y_test, y=y_test, mode='lines', name='Ideal Fit'))
    time.sleep(1)
    fig.show()

    # --- 4. Sales Distribution by Keyword Counts ---
    fig = px.scatter(data, x='Title_Keyword_Count', y='Sales', color='Rating',
                    title="Sales by Title Keyword Count",
                    labels={'Title_Keyword_Count': 'Keyword Count in Title', 'Sales': 'Total Sales'})
    time.sleep(2)
    fig.show()

    fig = px.scatter(data, x='Desc_Keyword_Count', y='Sales', color='Price',
                    title="Sales by Description Keyword Count",
                    labels={'Desc_Keyword_Count': 'Keyword Count in Description', 'Sales': 'Total Sales'})
    time.sleep(3)
    fig.show()

    # Calculate and print the mean of the sales
    mean_sales = y_test.mean()
    print(f"Mean Sales: {mean_sales}")

    # Calculate and print the R² score of the model
    r2 = r2_score(y_test, y_pred)
    print(f"R² Score: {r2}")

if __name__ == '__main__':
    run_analysis()

