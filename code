import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from collections import defaultdict

# --- Setup and Dictionaries ---
months = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}

st.title("Lundagård Article Scraper")
st.write("Scrape articles and calculate the weekly character counts.")

# --- UI: User Inputs (Replaces config.txt) ---
url = st.text_input("Start URL", "https://www.lundagard.se/2025/11/05/lundgrens-av-tekla-svensson-6/")
cutoff_date = st.date_input("Scrape until date:", datetime(2025, 10, 1))

# --- Application Logic ---
if st.button("Start Scraping"):
    
    # UI Elements for user feedback
    status_text = st.empty()
    
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session()
    articles = []
    weekly_counts = defaultdict(int)
    
    current_url = url
    cutoff_datetime = datetime.combine(cutoff_date, datetime.min.time())

    # 1. Scrape Articles
    with st.spinner("Scraping in progress... This may take a moment."):
        while current_url:
            status_text.text(f"Scraping: {current_url}")
            
            html = session.get(current_url, headers=headers).text
            soup = BeautifulSoup(html, "lxml")
            
            date_div = soup.find("div", class_="post-date-bd")
            if not date_div:
                break
                
            date_str = date_div.find("span").text.strip()
            parts = date_str.replace(",", "").split()
            year = int(parts[2])
            month = months[parts[1].lower()]
            day = int(parts[0])
            dt = datetime(year, month, day)
            
            if dt < cutoff_datetime:
                break
                
            date_formatted = dt.strftime("%Y-%m-%d")
            cats_div = soup.find("div", class_="post-cats-bd")
            categories = [a.text.strip() for a in cats_div.find_all("a")] if cats_div else []
            
            if 'Debatt' not in categories and 'Insändare' not in categories:
                num_images = 0
                character_count = 0
                
                post_featured = soup.find("div", class_="post-featured-image-bd")
                if post_featured:
                    num_images += len(post_featured.find_all("img"))
                    
                post_content = soup.find("div", class_="post-content-bd")
                if post_content:
                    num_images += len(post_content.find_all("img"))
                    for figure in post_content.find_all("figure"):
                        figure.decompose()
                    character_count += len(post_content.text)
                    
                total = (num_images * 300) + character_count
                
                # 2. Aggregate Weeks on the fly (Replaces weeks.py)
                year_iso, week_iso, _ = dt.isocalendar()
                weekly_counts[(year_iso, week_iso)] += total

            # Find next page
            prev_div = soup.find("div", class_="post-nav-prev")
            if prev_div and prev_div.find("a"):
                current_url = prev_div.find("a")["href"]
            else:
                break

    status_text.text("Scraping complete!")

    # --- UI: Display Results & Download ---
    if weekly_counts:
        st.success(f"Successfully processed data into {len(weekly_counts)} weeks.")
        
        # Convert to Pandas DataFrame for a nice web table and CSV export
        df = pd.DataFrame(
            [{"Year": y, "Week": w, "Total": t} for (y, w), t in sorted(weekly_counts.items())]
        )
        
        # Show a chart and the data table on the website
        st.bar_chart(data=df, x="Week", y="Total")
        st.dataframe(df, use_container_width=True)

        # Download Button
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download veckor.csv",
            data=csv_data,
            file_name='veckor.csv',
            mime='text/csv',
        )
    else:
        st.warning("No articles found matching the criteria.")
