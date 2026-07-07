import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# --- Setup ---
st.set_page_config(page_title="Lundagård Scraper", layout="wide")

# Initialize session state to remember scraped data between clicks
if "scraped_df" not in st.session_state:
    st.session_state.scraped_df = None

st.title("Lundagård Article Scraper (API Version)")

# --- STEP 1: Inputs & Configuration ---
st.header("1. Setup & Scrape")
col1, col2 = st.columns(2)

with col1:
    st.info("💡 API Mode: No Start URL needed. We fetch directly from the database.")
    cutoff_date = st.date_input("Scrape all articles back to:", datetime(2025, 10, 1))

with col2:
    # Allow users to easily modify the blacklist
    blacklist_input = st.text_input("Blacklisted Categories (comma-separated)", "Debatt, Insändare")
    blacklist = [tag.strip().lower() for tag in blacklist_input.split(",")]

# --- STEP 2: The Fast Scraper ---
if st.button("Start Scraping", type="primary"):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # Add the browser disguise to prevent getting blocked by security
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Fetch Categories first
    status_text.text("Connecting to database...")
    cat_url = "https://www.lundagard.se/wp-json/wp/v2/categories?per_page=100"
    
    try:
        cat_response = requests.get(cat_url, headers=headers).json()
        category_map = {cat['id']: cat['name'].lower() for cat in cat_response}
        category_map_display = {cat['id']: cat['name'] for cat in cat_response}
    except Exception as e:
        st.error(f"Failed to connect to the category database. Error: {e}")
        st.stop()

    articles = []
    page = 1
    
    # Format the date perfectly for the WordPress API (ISO 8601 format)
    cutoff_iso = f"{cutoff_date.strftime('%Y-%m-%d')}T00:00:00"

    with st.spinner("Fetching batches of 100 articles..."):
        while True:
            status_text.text(f"Fetching page {page}...")
            
            # Request 100 articles at a time, strictly after our cutoff date
            api_url = f"https://www.lundagard.se/wp-json/wp/v2/posts?per_page=100&page={page}&after={cutoff_iso}"
            response = requests.get(api_url, headers=headers)
            
            # Break if we've run out of pages or hit an error
            if response.status_code != 200:
                if response.status_code != 400: # 400 often just means we hit the end of the pages
                    st.warning(f"Stopped fetching. Server returned status: {response.status_code}")
                break
                
            try:
                posts = response.json()
            except Exception:
                st.error("Failed to parse JSON on this page. Stopping scraper.")
                break

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
                        
                    # Remove figures and count characters
                    for figure in soup.find_all("figure"):
                        figure.decompose()
                    character_count = len(soup.text)
                    
                    articles.append({
                        "Include": True, 
                        "Date": post['date'].split("T")[0], # Split '2025-11-05T08:00:00'
                        "Title": post['title']['rendered'], 
                        "Categories": ", ".join(post_cats_display),
                        "Images": num_images,
                        "Characters": character_count,
                        "URL": post['link']
                    })
            
            page += 1 # Move to the next batch of 100

    status_text.text(f"Scraping complete! Found {len(articles)} articles.")
    progress_bar.empty()
    
    # Save the data to session state so it persists
    if articles:
        st.session_state.scraped_df = pd.DataFrame(articles)
    else:
        st.warning("No articles found matching the criteria.")

# --- STEP 3: Review & Calculate ---
if st.session_state.scraped_df is not None:
    st.divider()
    st.header("2. Review Data")
    st.write("Uncheck 'Include' to remove an article. You can also manually edit the Image or Character counts.")
    
    # Display the interactive editor
    edited_df = st.data_editor(
        st.session_state.scraped_df,
        column_config={
            "Include": st.column_config.CheckboxColumn("Include", help="Select to include in calculation"),
            "URL": st.column_config.LinkColumn("Link")
        },
        disabled=["Date", "Title", "Categories", "URL"], # Lock columns they shouldn't edit
        hide_index=True,
        use_container_width=True
    )

    st.header("3. Final Results")
    if st.button("Calculate Totals", type="primary"):
        # Filter only included rows
        final_df = edited_df[edited_df["Include"] == True].copy()
        
        # Calculate Total Chars per article (Images * 300 + Characters)
        final_df["Total Score"] = (final_df["Images"] * 300) + final_df["Characters"]
        
        # Calculate Week and Year
        final_df['Date_Obj'] = pd.to_datetime(final_df['Date'])
        final_df['Year'] = final_df['Date_Obj'].dt.isocalendar().year
        final_df['Week'] = final_df['Date_Obj'].dt.isocalendar().week
        
        # Group by Year and Week
        weekly_summary = final_df.groupby(['Year', 'Week'])['Total Score'].sum().reset_index()
        total_all_time = final_df['Total Score'].sum()

        # Display Results
        col_res1, col_res2 = st.columns([2, 1])
        
        with col_res1:
            st.subheader("Week-by-Week Breakdown")
            st.dataframe(weekly_summary, hide_index=True, use_container_width=True)
            st.bar_chart(data=weekly_summary, x="Week", y="Total Score")
            
        with col_res2:
            st.subheader("Grand Total")
            st.metric(label="Total Calculated Characters", value=f"{total_all_time:,}")
            
            # Download buttons
            st.download_button(
                label="Download Weekly Summary (CSV)",
                data=weekly_summary.to_csv(index=False).encode('utf-8'),
                file_name='veckor.csv',
                mime='text/csv'
            )
