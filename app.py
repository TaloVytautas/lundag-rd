import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Lundagård Scraper", layout="wide")

if "scraped_df" not in st.session_state:
    st.session_state.scraped_df = None

st.title("Lundagård Article Scraper (API Version)")

# --- STEP 1: Inputs ---
st.header("1. Setup & Scrape")
col1, col2 = st.columns(2)

with col1:
    st.info("💡 API Mode: No Start URL needed. We fetch directly from the database.")
    cutoff_date = st.date_input("Scrape all articles back to:", datetime(2025, 10, 1))

with col2:
    blacklist_input = st.text_input("Blacklisted Categories (comma-separated)", "Debatt, Insändare")
    blacklist = [tag.strip().lower() for tag in blacklist_input.split(",")]

# --- STEP 2: The Fast Scraper ---
if st.button("Start Scraping", type="primary"):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # 1. Fetch Categories first (The API uses ID numbers for categories, so we need the map)
    status_text.text("Connecting to database...")
    cat_url = "https://www.lundagard.se/wp-json/wp/v2/categories?per_page=100"
    cat_response = requests.get(cat_url).json()
    category_map = {cat['id']: cat['name'].lower() for cat in cat_response}
    category_map_display = {cat['id']: cat['name'] for cat in cat_response}

    articles = []
    page = 1
    
    # Format the date perfectly for the WordPress API (ISO 8601 format)
    cutoff_iso = f"{cutoff_date.strftime('%Y-%m-%d')}T00:00:00"

    with st.spinner("Fetching batches of 100 articles..."):
        while True:
            status_text.text(f"Fetching page {page}...")
            
            # Request 100 articles at a time, strictly after our cutoff date
            api_url = f"https://www.lundagard.se/wp-json/wp/v2/posts?per_page=100&page={page}&after={cutoff_iso}"
            response = requests.get(api_url)
            
            # Break if we've run out of pages or hit an error
            if response.status_code != 200:
                break
                
            posts = response.json()
            if not posts:
                break # No more posts found

            for post in posts:
                # Map category IDs back to readable names
                post_cats_lower = [category_map.get(cid, "") for cid in post.get('categories', [])]
                post_cats_display = [category_map_display.get(cid, "Unknown") for cid in post.get('categories', [])]
                
                # Check Blacklist
                if not any(b in post_cats_lower for b in blacklist):
                    # Parse the raw HTML content returned by the API
                    html_content = post['content']['rendered']
                    soup = BeautifulSoup(html_content, "lxml")
                    
                    # Count Images (Body images + Featured image if one exists)
                    num_images = len(soup.find_all("img"))
                    if post.get('featured_media', 0) > 0:
                        num_images += 1
                        
                    # Remove figures and count characters, just like your original code
                    for figure in soup.find_all("figure"):
                        figure.decompose()
                    character_count = len(soup.text)
                    
                    articles.append({
                        "Include": True, 
                        "Date": post['date'].split("T")[0], # Split '2025-11-05T08:00:00'
                        "Title": post['title']['rendered'], # API returns clean titles
                        "Categories": ", ".join(post_cats_display),
                        "Images": num_images,
                        "Characters": character_count,
                        "URL": post['link']
                    })
            
            page += 1 # Move to the next batch of 100

    status_text.text(f"Scraping complete! Found {len(articles)} articles.")
    progress_bar.empty()
    
    if articles:
        st.session_state.scraped_df = pd.DataFrame(articles)
    else:
        st.warning("No articles found matching the criteria.")

# --- STEP 3: Review & Calculate ---
# (This remains exactly the same as the previous script)
if st.session_state.scraped_df is not None:
    st.divider()
    st.header("2. Review Data")
    
    edited_df = st.data_editor(
        st.session_state.scraped_df,
        column_config={
            "Include": st.column_config.CheckboxColumn("Include"),
            "URL": st.column_config.LinkColumn("Link")
        },
        disabled=["Date", "Title", "Categories", "URL"],
        hide_index=True,
        use_container_width=True
    )

    st.header("3. Final Results")
    if st.button("Calculate Totals", type="primary"):
        final_df = edited_df[edited_df["Include"] == True].copy()
        final_df["Total Score"] = (final_df["Images"] * 300) + final_df["Characters"]
        
        final_df['Date_Obj'] = pd.to_datetime(final_df['Date'])
        final_df['Year'] = final_df['Date_Obj'].dt.isocalendar().year
        final_df['Week'] = final_df['Date_Obj'].dt.isocalendar().week
        
        weekly_summary = final_df.groupby(['Year', 'Week'])['Total Score'].sum().reset_index()
        total_all_time = final_df['Total Score'].sum()

        col_res1, col_res2 = st.columns([2, 1])
        with col_res1:
            st.dataframe(weekly_summary, hide_index=True, use_container_width=True)
            st.bar_chart(data=weekly_summary, x="Week", y="Total Score")
        with col_res2:
            st.metric(label="Total Calculated Characters", value=f"{total_all_time:,}")
            st.download_button(
                label="Download Weekly Summary",
                data=weekly_summary.to_csv(index=False).encode('utf-8'),
                file_name='veckor.csv',
                mime='text/csv'
            )
