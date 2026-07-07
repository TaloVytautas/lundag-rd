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

st.title("Lundagård Article Scraper")

# --- STEP 1: Inputs & Configuration ---
st.header("1. Setup & Scrape")
col1, col2 = st.columns(2)

with col1:
    # Added a date range instead of a single cutoff date
    start_date = st.date_input("Start Date (Oldest article):", datetime(2025, 10, 1))
    end_date = st.date_input("End Date (Newest article):", datetime.now())

with col2:
    # Allow users to easily modify the blacklist
    blacklist_input = st.text_input("Blacklisted Categories (comma-separated)", "Debatt, Insändare")
    blacklist = [tag.strip().lower() for tag in blacklist_input.split(",")]

# --- STEP 2: The Fast Scraper ---
if st.button("Start Scraping", type="primary"):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # Browser disguise to prevent getting blocked by security
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Fetch Categories first
    status_text.text("Connecting to database...")
    cat_url = "https://www.lundagard.se/wp-json/wp/v2/categories?per_page=100"
    
    try:
        cat_response = requests.get(cat_url, headers=headers).json()
        category_map = {cat['id']: cat['name'].lower() for cat in cat_response}
