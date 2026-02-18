import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

# Add project root to path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings

# ==========================================
# 1. Page Config & Styling
# ==========================================
st.set_page_config(
    page_title="AI Portfolio Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a cleaner look
st.markdown("""
    <style>
    .big-font { font-size:20px !important; }
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. Data Loading Helper
# ==========================================
@st.cache_data
def load_data():
    data = {}
    
    # Load Feature Data (Core Portfolio)
    if settings.FEATURE_DATA_JSON.exists():
        with open(settings.FEATURE_DATA_JSON, "r") as f:
            data["features"] = json.load(f)
    
    # Load Market Data (Prices)
    if settings.MARKET_DATA_JSON.exists():
        with open(settings.MARKET_DATA_JSON, "r") as f:
            data["market"] = json.load(f)

    # Load Analysis (Discovery)
    if settings.PORTFOLIO_ANALYSIS_JSON.exists():
        with open(settings.PORTFOLIO_ANALYSIS_JSON, "r") as f:
            data["analysis"] = json.load(f)

    # Load Insights (LLM Text)
    if settings.INSIGHTS_JSON.exists():
        with open(settings.INSIGHTS_JSON, "r") as f:
            data["insights"] = json.load(f)

    # Load News
    if settings.NEWS_DATA_JSON.exists():
        with open(settings.NEWS_DATA_JSON, "r") as f:
            data["news"] = json.load(f)
            
    return data

data_store = load_data()

# ==========================================
# 3. Sidebar
# ==========================================
st.sidebar.title("🚀 AI Portfolio")
st.sidebar.markdown("---")
st.sidebar.info(f"**Data Source:** {settings.PORTFOLIO_CSV.name}")

if "features" in data_store:
    as_of = data_store["features"].get("as_of", "N/A")[:10]
    st.sidebar.caption(f"Last Updated: {as_of}")
else:
    st.sidebar.error("No data found. Please run the pipeline.")

# ==========================================
# 4. Main Dashboard Logic
# ==========================================

if "features" not in data_store:
    st.warning("⚠️ Feature data not found. Please run `python sc/src/feature_engineering.py` first.")
    st.stop()

# Prepare DataFrame
items = data_store["features"]["items"]
df = pd.DataFrame.from_dict(items, orient='index')

# --- HEADER METRICS ---
total_value = df["market_value"].sum()
top_sector = df.groupby("sector")["market_value"].sum().idxmax()
top_holding = df.loc[df["market_value"].idxmax()]["name"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Value", f"${total_value:,.2f}")
c2.metric("Top Sector", top_sector)
c3.metric("Top Holding", top_holding)
c4.metric("Total Positions", len(df))

st.markdown("---")

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🧠 AI Insights", "🌍 Discovery", "📰 News"])

# ------------------------------------------------------
# TAB 1: OVERVIEW
# ------------------------------------------------------
with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Sector Allocation")
        fig_sector = px.pie(df, values='market_value', names='sector', hole=0.4, 
                            color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_sector, use_container_width=True)

    with col2:
        st.subheader("Portfolio Composition")
        fig_tree = px.treemap(df, path=['sector', 'name'], values='market_value',
                              color='weight_pct', color_continuous_scale='Viridis')
        st.plotly_chart(fig_tree, use_container_width=True)

    st.subheader("Holdings Detail")
    
    # Format for display
    display_df = df[["name", "sector", "country", "quantity", "current_price", "market_value", "weight_pct"]].copy()
    display_df.columns = ["Name", "Sector", "Country", "Qty", "Price", "Value ($)", "Weight (%)"]
    
    st.dataframe(
        display_df.style.format({
            "Price": "${:.2f}", 
            "Value ($)": "${:,.2f}", 
            "Weight (%)": "{:.2f}%"
        }),
        use_container_width=True
    )

# ------------------------------------------------------
# TAB 2: AI INSIGHTS
# ------------------------------------------------------
with tab2:
    if "insights" in data_store:
        insights = data_store["insights"]
        
        # Risk Overview
        st.info(f"**Risk Overview:** {insights.get('risk_overview', 'N/A')}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🧐 Key Observations")
            for obs in insights.get("key_observations", []):
                st.markdown(f"- {obs}")
        
        with c2:
            st.markdown("### 📉 Volatility Context")
            st.write(insights.get("volatility_context", "N/A"))
            
            st.markdown("### 🐂 Market Sentiment")
            st.write(insights.get("market_sentiment_context", "N/A"))
            
    else:
        st.warning("No insights found. Run `python sc/src/insight_generator.py`.")

# ------------------------------------------------------
# TAB 3: DISCOVERY (New Candidates)
# ------------------------------------------------------
with tab3:
    st.header("🔍 AI Market Discovery")
    st.markdown("Candidates found via Google Search Grounding based on your portfolio gaps.")
    
    if "analysis" in data_store and "external_discovery" in data_store["analysis"]:
        discovery = data_store["analysis"]["external_discovery"]
        
        if not discovery:
            st.info("No discovery data available. Ensure you have an API key and ran `portfolio_analysis.py`.")
        else:
            col_a, col_b = st.columns(2)
            
            # Sector Peers
            with col_a:
                st.subheader(f"🎯 Sector Peers")
                peers = discovery.get("sector_peers", [])
                if peers:
                    for p in peers:
                        with st.expander(f"**{p.get('ticker')}** - {p.get('name')}"):
                            st.write(f"**Price:** {p.get('current_price')} {p.get('currency')}")
                            st.write(f"**Reason:** {p.get('reason')}")
                else:
                    st.write("No sector peers found.")

            # Country Peers
            with col_b:
                st.subheader(f"🌍 Country Opportunities")
                peers = discovery.get("country_peers", [])
                if peers:
                    for p in peers:
                        with st.expander(f"**{p.get('ticker')}** - {p.get('name')}"):
                            st.write(f"**Price:** {p.get('current_price')} {p.get('currency')}")
                            st.write(f"**Reason:** {p.get('reason')}")
                else:
                    st.write("No country peers found.")
    else:
        st.warning("Analysis data missing.")

# ------------------------------------------------------
# TAB 4: NEWS
# ------------------------------------------------------
with tab4:
    st.header("📰 Recent News & Sentiment")
    
    if "news" in data_store:
        news_items = data_store["news"].get("items", {})
        
        # Filter controls
        sentiment_filter = st.multiselect("Filter Sentiment", ["positive", "negative", "neutral"], default=["positive", "negative"])
        
        for ticker, data in news_items.items():
            stories = data.get("stories", [])
            agg_sentiment = data.get("aggregate_sentiment", {}).get("label", "neutral")
            
            if agg_sentiment not in sentiment_filter:
                continue
                
            if stories:
                with st.expander(f"**{ticker}** ({len(stories)} stories) - Sentiment: {agg_sentiment.upper()}"):
                    for story in stories:
                        # Color code sentiment
                        s_label = story.get('sentiment_label', 'neutral').lower()
                        color = "green" if s_label == "positive" else "red" if s_label == "negative" else "gray"
                        
                        st.markdown(f"**{story.get('title')}**")
                        st.caption(f"📅 {story.get('published_at')} | :{color}[{s_label.upper()}]")
                        st.write(story.get('summary'))
                        if story.get('url'):
                            st.markdown(f"[Read Source]({story.get('url')})")
                        st.divider()
    else:
        st.warning("No news data found. Run `python sc/src/news_pipeline.py`.")