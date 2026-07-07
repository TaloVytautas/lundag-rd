import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# --- Setup ---
st.set_page_config(page_title="Lundagård Scraper", layout="wide")

months = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}

# Initialize session state to remember scraped data between clicks
if "scraped_df" not in st.session_state:
    st.session_state.scraped_df = None

st.title("Lundagård Article Scraper & Calculator")

# --- STEP 1: Inputs & Configuration ---
st.header("1. Setup & Scrape")
col1, col2 = st.columns(2)

with col1:
    url = st.text_input("Start URL", "https://www.lundagard.se/2025/11/05/lundgrens-av-tekla-svensson-6/")
    cutoff_date = st.date_input("Scrape until date:", datetime(2025, 10, 1))

with col2:
    # Allow users to easily modify the blacklist
    blacklist_input = st.text_input("Blacklisted Categories (comma-separated)", "Debatt, Insändare")
    blacklist = [tag.strip().lower() for tag in blacklist_input.split(",")]

# --- STEP 2: The Scraper ---
if st.button("Start Scraping", type="primary"):
    status_text = st.empty()
    
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session()
    articles = []
    
    current_url = url
    cutoff_datetime = datetime.combine(cutoff_date, datetime.min.time())

    with st.spinner("Scraping in progress..."):
        while current_url:
            status_text.text(f"Scraping: {current_url}")
            html = session.get(current_url, headers=headers).text
            soup = BeautifulSoup(html, "lxml")
            
            date_div = soup.find("div", class_="post-date-bd")
            if not date_div: break
                
            date_str = date_div.find("span").text.strip()
            parts = date_str.replace(",", "").split()
            dt = datetime(int(parts[2]), months[parts[1].lower()], int(parts[0]))
            
            if dt < cutoff_datetime: break
                
            cats_div = soup.find("div", class_="post-cats-bd")
            categories = [a.text.strip() for a in cats_div.find_all("a")] if cats_div else []
            categories_lower = [c.lower() for c in categories]
            
            # Check if any category is in the blacklist
            if not any(b in categories_lower for b in blacklist):
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
                
                # Append to our list. We add an "Include" boolean for the checkbox.
                articles.append({
                    "Include": True, 
                    "Date": dt.strftime("%Y-%m-%d"),
                    "Title": soup.find("h1", class_="entry-title").text.strip(),
                    "Categories": ", ".join(categories),
                    "Images": num_images,
                    "Characters": character_count,
                    "URL": current_url
                })

            prev_div = soup.find("div", class_="post-nav-prev")
            if prev_div and prev_div.find("a"):
                current_url = prev_div.find("a")["href"]
            else:
                break

    status_text.text("Scraping complete!")
    
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
