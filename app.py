# ============================================================
#  NMS STOCK DASHBOARD - FULL WEB APPLICATION
#  (Landing Page + Filters + Tabs + Heatmaps)
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime, timedelta
import numpy as np

# --- Page Configuration ---
st.set_page_config(
    page_title="NMS Stock Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for better styling ---
st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1a73e8; }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 4px solid #1a73e8; }
    .metric-value { font-size: 2rem; font-weight: bold; }
    .metric-label { font-size: 0.9rem; color: #5f6368; }
    .tab-header { font-size: 1.5rem; font-weight: bold; margin-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- Connect to BigQuery using Streamlit Secrets ---
def init_client():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        return bigquery.Client(
            project=st.secrets["gcp_service_account"]["project_id"],
            credentials=credentials
        )
    except KeyError:
        return bigquery.Client(project='nms-dasboard')

client = init_client()

# --- Load Data with Caching ---
@st.cache_data(ttl=3600)
def load_data():
    query = """
    SELECT 
        Order_Type,
        District,
        Item_Description,
        Quantity_Shipped,
        Order_Quantity,
        Lot_Expiration_Date,
        Ship_Confirm_Date,
        Selling_Price,
        List_Price,
        Ship_To_Facility_Name,
        Ship_To_Facility_Code,
        Funding_Source,
        Cycle,
        Month,
        category
    FROM `nms-dasboard.nms_data.all_nms_data`
    """
    df = client.query(query).to_dataframe()
    
    for col in ['Quantity_Shipped', 'Order_Quantity', 'Selling_Price', 'List_Price']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.replace(' ', '')
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['Ship_Confirm_Date'] = pd.to_datetime(df['Ship_Confirm_Date'], errors='coerce')
    df['Lot_Expiration_Date'] = pd.to_datetime(df['Lot_Expiration_Date'], errors='coerce')
    
    df['fulfilment_rate'] = (df['Quantity_Shipped'] / df['Order_Quantity'].replace(0, np.nan)) * 100
    df['fulfilment_rate'] = df['fulfilment_rate'].clip(0, 100)
    
    return df

df = load_data()

# --- Sidebar Filters ---
st.sidebar.title("🔍 Filters")

region_mapping = {
    'Fort Portal': ['KABAROLE', 'KYENJOJO', 'KAMWENGE', 'BUNDIBUGYO', 'NTOROKO'],
    'Mubende': ['MUBENDE', 'KASANDA', 'KYANKWANZI', 'SEMBABULE'],
    'Hoima': ['HOIMA', 'MASINDI', 'KIKUUBE', 'BULIISA', 'KIRYANDONGO'],
    'Other': []
}

all_regions = ['All'] + list(region_mapping.keys())
selected_region = st.sidebar.selectbox("🌍 Select Region", all_regions)

if selected_region == 'All':
    available_districts = sorted(df['District'].dropna().unique())
else:
    available_districts = sorted([d for d in region_mapping.get(selected_region, []) if d in df['District'].values])
    if not available_districts:
        available_districts = ['No districts available']

selected_district = st.sidebar.selectbox("🏛️ Select District", ['All'] + available_districts)

if selected_district != 'All':
    available_facilities = sorted(df[df['District'] == selected_district]['Ship_To_Facility_Name'].dropna().unique())
else:
    available_facilities = sorted(df['Ship_To_Facility_Name'].dropna().unique())

selected_facility = st.sidebar.selectbox("🏥 Select Facility", ['All'] + available_facilities[:50])

categories = sorted(df['category'].dropna().unique())
selected_category = st.sidebar.selectbox("📂 Item Category", ['All'] + list(categories))

# --- Apply Filters ---
filtered_df = df.copy()

if selected_region != 'All':
    region_districts = region_mapping.get(selected_region, [])
    if region_districts:
        filtered_df = filtered_df[filtered_df['District'].isin(region_districts)]

if selected_district != 'All':
    filtered_df = filtered_df[filtered_df['District'] == selected_district]

if selected_facility != 'All':
    filtered_df = filtered_df[filtered_df['Ship_To_Facility_Name'] == selected_facility]

if selected_category != 'All':
    filtered_df = filtered_df[filtered_df['category'] == selected_category]

# --- Compute Metrics ---
total_qty = filtered_df['Quantity_Shipped'].sum()
total_value = (filtered_df['Quantity_Shipped'] * filtered_df['Selling_Price']).sum()
total_order_qty = filtered_df['Order_Quantity'].sum()
fulfilment_rate = (total_qty / total_order_qty * 100) if total_order_qty > 0 else 0

today = datetime.now()
expiring_soon = filtered_df[
    (filtered_df['Lot_Expiration_Date'] < (today + timedelta(days=90))) &
    (filtered_df['Lot_Expiration_Date'] > today)
]['Lot_Expiration_Date'].count()

# --- HEADER ---
st.markdown('<p class="main-header">📦 NMS Stock Dashboard</p>', unsafe_allow_html=True)
st.caption(f"Data last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Showing {len(filtered_df):,} records")

# --- METRICS ROW ---
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">📦 Total Stock Shipped</div>
        <div class="metric-value">{total_qty:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">💰 Total Value (UGX)</div>
        <div class="metric-value">{total_value:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {'red' if expiring_soon > 0 else 'green'};">
        <div class="metric-label">⚠️ Expiring in 90 Days</div>
        <div class="metric-value" style="color: {'red' if expiring_soon > 0 else 'green'};">{expiring_soon:,}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {'orange' if fulfilment_rate < 80 else 'green'};">
        <div class="metric-label">📊 Fulfilment Rate</div>
        <div class="metric-value">{fulfilment_rate:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    top_district = filtered_df.groupby('District')['Quantity_Shipped'].sum().idxmax() if not filtered_df.empty else 'N/A'
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🏆 Top District</div>
        <div class="metric-value">{top_district}</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Stock Overview",
    "📍 Heatmap View",
    "📦 Order Fulfilment",
    "🏥 Facility Detail"
])

# ============================================================
# TAB 1: STOCK OVERVIEW
# ============================================================
with tab1:
    st.markdown('<p class="tab-header">📊 Stock Overview</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        district_data = filtered_df.groupby('District')['Quantity_Shipped'].sum().reset_index()
        if not district_data.empty:
            fig1 = px.bar(
                district_data,
                x='District',
                y='Quantity_Shipped',
                title='Stock by District',
                color='Quantity_Shipped',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        cat_data = filtered_df.groupby('category')['Quantity_Shipped'].sum().reset_index()
        if not cat_data.empty:
            fig2 = px.pie(
                cat_data,
                values='Quantity_Shipped',
                names='category',
                title='Stock by Category'
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    expiry_data = filtered_df[filtered_df['Lot_Expiration_Date'].notna()]
    if not expiry_data.empty:
        fig3 = px.histogram(
            expiry_data,
            x='Lot_Expiration_Date',
            nbins=30,
            title='Distribution of Lot Expiry Dates',
            color_discrete_sequence=['#ff6b6b']
        )
        st.plotly_chart(fig3, use_container_width=True)
    
    st.subheader("🏷️ Top Items by Quantity")
    top_items = filtered_df.groupby('Item_Description')['Quantity_Shipped'].sum().reset_index().sort_values('Quantity_Shipped', ascending=False).head(10)
    st.dataframe(top_items, use_container_width=True)

# ============================================================
# TAB 2: HEATMAP VIEW
# ============================================================
with tab2:
    st.markdown('<p class="tab-header">📍 Heatmap View (Facility Stock Levels)</p>', unsafe_allow_html=True)
    
    heatmap_regions = ['Fort Portal', 'Mubende', 'Hoima']
    selected_heatmap_region = st.selectbox("Select Region for Heatmap", heatmap_regions)
    
    region_districts = region_mapping.get(selected_heatmap_region, [])
    heatmap_df = df[df['District'].isin(region_districts)].copy()
    
    if heatmap_df.empty:
        st.warning(f"No data available for {selected_heatmap_region} region.")
    else:
        heatmap_data = heatmap_df.groupby(['Ship_To_Facility_Name', 'District'])['Quantity_Shipped'].sum().reset_index()
        if not heatmap_data.empty:
            fig_heatmap = px.density_heatmap(
                heatmap_data,
                x='District',
                y='Ship_To_Facility_Name',
                z='Quantity_Shipped',
                title=f'Stock Levels by Facility in {selected_heatmap_region}',
                color_continuous_scale='RdYlGn',
                height=500
            )
            fig_heatmap.update_layout(
                xaxis_title='District',
                yaxis_title='Facility',
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)
            st.subheader("📋 Facility Stock Data")
            st.dataframe(
                heatmap_data.sort_values('Quantity_Shipped', ascending=False),
                use_container_width=True
            )
        else:
            st.info("No facility-level data available for this region.")

# ============================================================
# TAB 3: ORDER FULFILMENT
# ============================================================
with tab3:
    st.markdown('<p class="tab-header">📦 Order Fulfilment Analysis</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Ordered", f"{filtered_df['Order_Quantity'].sum():,.0f}")
        st.metric("Total Shipped", f"{filtered_df['Quantity_Shipped'].sum():,.0f}")
        st.metric("Fulfilment Rate", f"{fulfilment_rate:.1f}%")
    
    with col2:
        fulfilment_by_district = filtered_df.groupby('District').apply(
            lambda g: pd.Series({
                'order_qty': g['Order_Quantity'].sum(),
                'shipped_qty': g['Quantity_Shipped'].sum()
            })
        ).reset_index()
        fulfilment_by_district['fulfilment_rate'] = (fulfilment_by_district['shipped_qty'] / fulfilment_by_district['order_qty'].replace(0, np.nan)) * 100
        fulfilment_by_district['fulfilment_rate'] = fulfilment_by_district['fulfilment_rate'].clip(0, 100)
        fig_fulfilment = px.bar(
            fulfilment_by_district,
            x='District',
            y='fulfilment_rate',
            title='Fulfilment Rate by District',
            color='fulfilment_rate',
            color_continuous_scale='RdYlGn',
            range_color=[0, 100]
        )
        st.plotly_chart(fig_fulfilment, use_container_width=True)
    
    gap_data = filtered_df.groupby('District')[['Order_Quantity', 'Quantity_Shipped']].sum().reset_index()
    gap_data['gap'] = gap_data['Order_Quantity'] - gap_data['Quantity_Shipped']
    fig_gap = px.bar(
        gap_data,
        x='District',
        y=['Order_Quantity', 'Quantity_Shipped'],
        title='Order vs Shipped Quantity by District',
        barmode='group'
    )
    st.plotly_chart(fig_gap, use_container_width=True)

# ============================================================
# TAB 4: FACILITY DETAIL
# ============================================================
with tab4:
    st.markdown('<p class="tab-header">🏥 Facility-Level Detail</p>', unsafe_allow_html=True)
    
    facility_list = sorted(filtered_df['Ship_To_Facility_Name'].dropna().unique())
    selected_facility_detail = st.selectbox("Select a Facility", facility_list)
    
    if selected_facility_detail:
        facility_data = filtered_df[filtered_df['Ship_To_Facility_Name'] == selected_facility_detail]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Shipped", f"{facility_data['Quantity_Shipped'].sum():,.0f}")
        with col2:
            st.metric("Total Value", f"{facility_data['Quantity_Shipped'].sum() * facility_data['Selling_Price'].mean():,.0f}")
        with col3:
            st.metric("Fulfilment Rate", f"{(facility_data['Quantity_Shipped'].sum() / facility_data['Order_Quantity'].sum() * 100) if facility_data['Order_Quantity'].sum() > 0 else 0:.1f}%")
        
        st.subheader("📋 Items Received by This Facility")
        st.dataframe(
            facility_data[['Item_Description', 'Order_Quantity', 'Quantity_Shipped', 'Lot_Expiration_Date', 'category']],
            use_container_width=True
        )
        
        timeline = facility_data.groupby(pd.Grouper(key='Ship_Confirm_Date', freq='M'))['Quantity_Shipped'].sum().reset_index()
        if not timeline.empty:
            fig_timeline = px.line(
                timeline,
                x='Ship_Confirm_Date',
                y='Quantity_Shipped',
                title=f'Stock Receipts Over Time - {selected_facility_detail}',
                markers=True
            )
            st.plotly_chart(fig_timeline, use_container_width=True)

st.divider()
st.caption("📦 NMS Stock Dashboard | Built with Streamlit + BigQuery | Data refreshes every hour")
