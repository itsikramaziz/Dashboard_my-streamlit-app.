import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Simpaisa SR Dashboard",
    page_icon="🏦",
    layout="wide"
)

# Required columns - ONLY these will be kept
REQUIRED_COLUMNS = [
    'Account',
    'Merchant ID', 
    'Amount',
    'Remit. Timestamp',
    'Issue Timestamp',
    'State'
]

# State colors
STATE_COLORS = {
    'Remitted': '#10b981',
    'Published': '#3b82f6',
    'Rejected': '#ef4444',
    'On hold': '#f59e0b',
    'Stuck': '#dc2626',
    'In review': '#8b5cf6',
    'In process': '#06b6d4',
    'Aml review': '#ec4899',
    'No config': '#6b7280'
}

def normalize_state(state):
    """Normalize state names to standard format"""
    if pd.isna(state):
        return 'Unknown'
    
    state_lower = str(state).strip().lower()
    
    # Map variations to standard names
    state_map = {
        'remitted': 'Remitted',
        'published': 'Published',
        'rejected': 'Rejected',
        'on hold': 'On hold',
        'onhold': 'On hold',
        'stuck': 'Stuck',
        'in review': 'In review',
        'inreview': 'In review',
        'in process': 'In process',
        'inprocess': 'In process',
        'aml review': 'Aml review',
        'amlreview': 'Aml review',
        'no config': 'No config',
        'noconfig': 'No config'
    }
    
    return state_map.get(state_lower, state.capitalize())

def clean_dataframe(df):
    """Keep only required columns and normalize column names"""
    # Normalize column names (handle case variations)
    df.columns = df.columns.str.strip()
    
    # Create column mapping (case-insensitive)
    column_mapping = {}
    for col in df.columns:
        for req_col in REQUIRED_COLUMNS:
            if col.lower() == req_col.lower():
                column_mapping[col] = req_col
                break
    
    # Rename columns
    df = df.rename(columns=column_mapping)
    
    # Keep only required columns that exist
    existing_cols = [col for col in REQUIRED_COLUMNS if col in df.columns]
    df = df[existing_cols]
    
    return df

def process_files(uploaded_files):
    """Process uploaded Excel or CSV files and combine data"""
    all_data = []
    
    for file in uploaded_files:
        try:
            # Read Excel or CSV file
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Clean dataframe - keep only required columns
            df = clean_dataframe(df)
            
            # Add to combined data
            all_data.append(df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {str(e)}")
    
    if not all_data:
        return None
    
    # Combine all dataframes
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Normalize state names
    if 'State' in combined_df.columns:
        combined_df['State'] = combined_df['State'].apply(normalize_state)
    
    # Convert Amount to numeric
    if 'Amount' in combined_df.columns:
        combined_df['Amount'] = pd.to_numeric(combined_df['Amount'], errors='coerce').fillna(0)
    
    return combined_df

def calculate_merchant_stats(df, merchant_id):
    """Calculate statistics for a specific merchant"""
    merchant_data = df[df['Merchant ID'] == merchant_id].copy()
    
    total_txns = len(merchant_data)
    
    # Success = Only Remitted
    success_txns = len(merchant_data[merchant_data['State'] == 'Remitted'])
    success_rate = (success_txns / total_txns * 100) if total_txns > 0 else 0
    
    # Amounts
    total_amount = merchant_data['Amount'].sum()
    success_amount = merchant_data[merchant_data['State'] == 'Remitted']['Amount'].sum()
    
    # State breakdown
    state_counts = merchant_data['State'].value_counts().to_dict()
    state_amounts = merchant_data.groupby('State')['Amount'].sum().to_dict()
    
    return {
        'merchant_id': merchant_id,
        'total_txns': total_txns,
        'success_txns': success_txns,
        'success_rate': round(success_rate, 2),
        'total_amount': total_amount,
        'success_amount': success_amount,
        'state_counts': state_counts,
        'state_amounts': state_amounts
    }

def format_currency(amount):
    """Format amount as Pakistani currency"""
    return f"Rs {amount:,.0f}"

# Title
st.title("🏦 Simpaisa SR Dashboard")
st.markdown("---")

# File upload
uploaded_files = st.file_uploader(
    "Upload Excel or CSV Files",
    type=['xlsx', 'xls', 'csv'],
    accept_multiple_files=True,
    help="Upload one or more Excel or CSV files containing merchant transaction data"
)

if uploaded_files:
    with st.spinner("Processing files..."):
        df = process_files(uploaded_files)
    
    if df is not None and not df.empty:
        st.success(f"✅ Processed {len(uploaded_files)} file(s) with {len(df)} total transactions")
        
        # Show cleaned columns info
        with st.expander("📋 Data Info"):
            st.write(f"**Columns kept:** {', '.join(df.columns.tolist())}")
            st.write(f"**Total rows:** {len(df)}")
            st.write(f"**Unique merchants:** {df['Merchant ID'].nunique()}")
        
        # Get unique merchants
        merchants = df['Merchant ID'].unique()
        
        # Calculate overall stats
        total_txns = len(df)
        success_txns = len(df[df['State'] == 'Remitted'])
        overall_sr = (success_txns / total_txns * 100) if total_txns > 0 else 0
        total_amount = df['Amount'].sum()
        success_amount = df[df['State'] == 'Remitted']['Amount'].sum()
        
        # Overall Stats Banner
        st.markdown("### 🌐 Overall Statistics")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Merchants", len(merchants))
        with col2:
            st.metric("Overall SR", f"{overall_sr:.2f}%")
        with col3:
            st.metric("Total Transactions", f"{total_txns:,}")
        with col4:
            st.metric("Total Amount", format_currency(total_amount))
        with col5:
            st.metric("Remitted Amount", format_currency(success_amount))
        
        st.markdown("---")
        
        # 📸 SCREENSHOT VIEW BUTTON
        if st.button("📸 Show All Merchants Summary (Screenshot View)", use_container_width=True, type="primary"):
            st.markdown("---")
            st.markdown("<h2 style='text-align: center;'>📊 All Merchants Summary - Screenshot Ready</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #6b7280;'>Use Ctrl+(-) to zoom out for better fit</p>", unsafe_allow_html=True)
            st.markdown("---")
            
            # Create grid: 3 columns x 2 rows = 6 merchants per view
            num_merchants = len(merchants)
            
            # Process in batches of 6
            for batch_start in range(0, num_merchants, 6):
                batch_end = min(batch_start + 6, num_merchants)
                batch_merchants = merchants[batch_start:batch_end]
                
                # First row - 3 merchants
                if len(batch_merchants) >= 1:
                    cols_row1 = st.columns(3)
                    
                    for idx in range(min(3, len(batch_merchants))):
                        merchant = batch_merchants[idx]
                        merchant_stats = calculate_merchant_stats(df, merchant)
                        
                        with cols_row1[idx]:
                            # Merchant Card
                            sr = merchant_stats['success_rate']
                            border_color = '#10b981' if sr >= 70 else '#f59e0b' if sr >= 50 else '#ef4444'
                            
                            st.markdown(f"""
                            <div style='border: 3px solid {border_color}; border-radius: 12px; 
                                        padding: 12px; background: #f8f9fa;'>
                                <h4 style='margin: 0 0 8px 0; text-align: center; color: white; 
                                           font-size: 0.95rem; background: {border_color}; 
                                           padding: 8px; border-radius: 6px;'>
                                    🏢 {merchant}
                                </h4>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # SR Display - Compact
                            st.markdown(f"""
                            <div style='text-align: center; padding: 8px; background: {border_color}; 
                                        border-radius: 8px; margin: 5px 0;'>
                                <h2 style='margin: 0; color: white; font-size: 1.5rem;'>{sr:.1f}%</h2>
                                <p style='margin: 0; color: white; font-size: 0.65rem; font-weight: bold;'>SUCCESS RATE</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Quick Stats
                            st.markdown(f"""
                            <div style='background: white; padding: 8px; border-radius: 6px; 
                                        font-size: 0.75rem; text-align: center; margin: 5px 0;'>
                                <b>Total:</b> {merchant_stats['total_txns']:,} | 
                                <b>Success:</b> {merchant_stats['success_txns']:,}<br>
                                <b>Amount:</b> {format_currency(merchant_stats['total_amount'])}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # State Breakdown Boxes
                            state_items = list(merchant_stats['state_counts'].items())
                            st.markdown("<div style='margin: 8px 0;'>", unsafe_allow_html=True)
                            for state, count in state_items:
                                color = STATE_COLORS.get(state, '#6b7280')
                                amount = merchant_stats['state_amounts'].get(state, 0)
                                
                                st.markdown(f"""
                                <div style='display: flex; justify-content: space-between; 
                                            align-items: center; padding: 6px 10px; margin: 3px 0;
                                            background: white; border-left: 4px solid {color}; 
                                            border-radius: 4px; font-size: 0.75rem;'>
                                    <span style='font-weight: bold; color: #374151;'>{state}</span>
                                    <span style='color: #6b7280;'><b>{count}</b></span>
                                </div>
                                """, unsafe_allow_html=True)
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                            # Bar Chart - With Total label
                            chart_df = pd.DataFrame({
                                'State': list(merchant_stats['state_counts'].keys()),
                                'Count': list(merchant_stats['state_counts'].values())
                            })
                            
                            # Add Total column
                            total_count = chart_df['Count'].sum()
                            chart_df_with_total = pd.concat([
                                chart_df,
                                pd.DataFrame({'State': ['TOTAL'], 'Count': [total_count]})
                            ], ignore_index=True)
                            
                            # Create color list with blue for total
                            colors_list = [STATE_COLORS.get(state, '#6b7280') for state in chart_df['State']] + ['#3b82f6']
                            
                            fig_bar = go.Figure(data=[go.Bar(
                                x=chart_df_with_total['State'],
                                y=chart_df_with_total['Count'],
                                marker=dict(color=colors_list),
                                text=chart_df_with_total['Count'],
                                textposition='outside',
                                textfont=dict(size=9, color='white'),
                                width=0.5
                            )])
                            fig_bar.update_layout(
                                height=170,
                                margin=dict(l=5, r=5, t=5, b=40),
                                xaxis=dict(
                                    title='', 
                                    tickangle=-45, 
                                    tickfont=dict(size=7),
                                    fixedrange=True
                                ),
                                yaxis=dict(
                                    title='', 
                                    showticklabels=False, 
                                    showgrid=False,
                                    fixedrange=True
                                ),
                                showlegend=False,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                bargap=0.25,
                                autosize=False
                            )
                            
                            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
                
                # Second row - next 3 merchants
                if len(batch_merchants) > 3:
                    st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
                    cols_row2 = st.columns(3)
                    
                    for idx in range(3, min(6, len(batch_merchants))):
                        merchant = batch_merchants[idx]
                        merchant_stats = calculate_merchant_stats(df, merchant)
                        
                        with cols_row2[idx - 3]:
                            # Same structure as row 1
                            sr = merchant_stats['success_rate']
                            border_color = '#10b981' if sr >= 70 else '#f59e0b' if sr >= 50 else '#ef4444'
                            
                            st.markdown(f"""
                            <div style='border: 3px solid {border_color}; border-radius: 12px; 
                                        padding: 12px; background: #f8f9fa;'>
                                <h4 style='margin: 0 0 8px 0; text-align: center; color: white; 
                                           font-size: 0.95rem; background: {border_color}; 
                                           padding: 8px; border-radius: 6px;'>
                                    🏢 {merchant}
                                </h4>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # SR Display - Compact
                            st.markdown(f"""
                            <div style='text-align: center; padding: 8px; background: {border_color}; 
                                        border-radius: 8px; margin: 5px 0;'>
                                <h2 style='margin: 0; color: white; font-size: 1.5rem;'>{sr:.1f}%</h2>
                                <p style='margin: 0; color: white; font-size: 0.65rem; font-weight: bold;'>SUCCESS RATE</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.markdown(f"""
                            <div style='background: white; padding: 8px; border-radius: 6px; 
                                        font-size: 0.75rem; text-align: center; margin: 5px 0;'>
                                <b>Total:</b> {merchant_stats['total_txns']:,} | 
                                <b>Success:</b> {merchant_stats['success_txns']:,}<br>
                                <b>Amount:</b> {format_currency(merchant_stats['total_amount'])}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            state_items = list(merchant_stats['state_counts'].items())
                            st.markdown("<div style='margin: 8px 0;'>", unsafe_allow_html=True)
                            for state, count in state_items:
                                color = STATE_COLORS.get(state, '#6b7280')
                                
                                st.markdown(f"""
                                <div style='display: flex; justify-content: space-between; 
                                            align-items: center; padding: 6px 10px; margin: 3px 0;
                                            background: white; border-left: 4px solid {color}; 
                                            border-radius: 4px; font-size: 0.75rem;'>
                                    <span style='font-weight: bold; color: #374151;'>{state}</span>
                                    <span style='color: #6b7280;'><b>{count}</b></span>
                                </div>
                                """, unsafe_allow_html=True)
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                            # Bar Chart - Fixed size container
                            # Bar Chart - With Total label
                            chart_df = pd.DataFrame({
                                'State': list(merchant_stats['state_counts'].keys()),
                                'Count': list(merchant_stats['state_counts'].values())
                            })
                            
                            # Add Total column
                            total_count = chart_df['Count'].sum()
                            chart_df_with_total = pd.concat([
                                chart_df,
                                pd.DataFrame({'State': ['TOTAL'], 'Count': [total_count]})
                            ], ignore_index=True)
                            
                            # Create color list with blue for total
                            colors_list = [STATE_COLORS.get(state, '#6b7280') for state in chart_df['State']] + ['#3b82f6']
                            
                            fig_bar = go.Figure(data=[go.Bar(
                                x=chart_df_with_total['State'],
                                y=chart_df_with_total['Count'],
                                marker=dict(color=colors_list),
                                text=chart_df_with_total['Count'],
                                textposition='outside',
                                textfont=dict(size=9, color='white'),
                                width=0.5
                            )])
                            fig_bar.update_layout(
                                height=170,
                                margin=dict(l=5, r=5, t=5, b=40),
                                xaxis=dict(
                                    title='', 
                                    tickangle=-45, 
                                    tickfont=dict(size=7),
                                    fixedrange=True
                                ),
                                yaxis=dict(
                                    title='', 
                                    showticklabels=False, 
                                    showgrid=False,
                                    fixedrange=True
                                ),
                                showlegend=False,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                bargap=0.25,
                                autosize=False
                            )
                            
                            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
                
                # Page separator
                if batch_end < num_merchants:
                    st.markdown("---")
                    st.markdown(f"<p style='text-align: center; color: #6b7280;'>⬇️ Scroll for more ({batch_end}/{num_merchants} merchants shown)</p>", unsafe_allow_html=True)
                    st.markdown("---")
            
            st.success("✅ Summary Complete! Zoom out (Ctrl+-) and take screenshot!")
            st.markdown("---")
        
        # Merchant selector
        st.markdown("### 🏢 Select Merchant")
        
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col2:
            selected_merchant = st.selectbox(
                "Choose Merchant",
                merchants,
                format_func=lambda x: f"Merchant: {x}"
            )
        
        # Calculate merchant stats
        stats = calculate_merchant_stats(df, selected_merchant)
        
        st.markdown(f"## Merchant: **{selected_merchant}**")
        st.markdown("---")
        
        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div style='background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                        padding: 20px; border-radius: 10px; text-align: center;'>
                <h3 style='color: white; margin: 0;'>Success Rate</h3>
                <h1 style='color: white; margin: 10px 0;'>{:.2f}%</h1>
                <p style='color: rgba(255,255,255,0.8); margin: 0;'>{} / {} txns</p>
            </div>
            """.format(stats['success_rate'], stats['success_txns'], stats['total_txns']), 
            unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div style='background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); 
                        padding: 20px; border-radius: 10px; text-align: center;'>
                <h3 style='color: white; margin: 0;'>Total Transactions</h3>
                <h1 style='color: white; margin: 10px 0;'>{:,}</h1>
                <p style='color: rgba(255,255,255,0.8); margin: 0;'>All states</p>
            </div>
            """.format(stats['total_txns']), 
            unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div style='background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); 
                        padding: 20px; border-radius: 10px; text-align: center;'>
                <h3 style='color: white; margin: 0;'>Total Amount</h3>
                <h1 style='color: white; margin: 10px 0; font-size: 1.8rem;'>{}</h1>
                <p style='color: rgba(255,255,255,0.8); margin: 0;'>All transactions</p>
            </div>
            """.format(format_currency(stats['total_amount'])), 
            unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div style='background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                        padding: 20px; border-radius: 10px; text-align: center;'>
                <h3 style='color: white; margin: 0;'>Remitted Amount</h3>
                <h1 style='color: white; margin: 10px 0; font-size: 1.8rem;'>{}</h1>
                <p style='color: rgba(255,255,255,0.8); margin: 0;'>Only Remitted</p>
            </div>
            """.format(format_currency(stats['success_amount'])), 
            unsafe_allow_html=True)
        
        st.markdown("---")
        
        # State Breakdown
        st.markdown("### 📦 Transaction States Breakdown")
        
        # Create state boxes
        state_cols = st.columns(5)
        merchant_state_items = list(stats['state_counts'].items())
        
        for idx, (state, count) in enumerate(merchant_state_items):
            col_idx = idx % 5
            amount = stats['state_amounts'].get(state, 0)
            percentage = (count / stats['total_txns'] * 100) if stats['total_txns'] > 0 else 0
            color = STATE_COLORS.get(state, '#6b7280')
            
            with state_cols[col_idx]:
                st.markdown(f"""
                <div style='border: 3px solid {color}; border-radius: 10px; padding: 15px; 
                            margin-bottom: 10px; background: white;'>
                    <div style='width: 15px; height: 15px; background: {color}; 
                                border-radius: 50%; margin-bottom: 10px;'></div>
                    <h4 style='margin: 5px 0; color: #374151;'>{state}</h4>
                    <h2 style='margin: 5px 0; color: #1f2937;'>{count}</h2>
                    <p style='margin: 2px 0; color: #6b7280; font-size: 0.85rem;'>{format_currency(amount)}</p>
                    <p style='margin: 2px 0; color: #9ca3af; font-size: 0.75rem;'>{percentage:.1f}% of total</p>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Charts
        st.markdown("### 📈 Visualizations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Pie chart
            fig_pie = go.Figure(data=[go.Pie(
                labels=list(stats['state_counts'].keys()),
                values=list(stats['state_counts'].values()),
                marker=dict(colors=[STATE_COLORS.get(state, '#6b7280') for state in stats['state_counts'].keys()]),
                hole=0.3
            )])
            fig_pie.update_layout(
                title="Transaction Distribution by State",
                height=400
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Bar chart
            state_df = pd.DataFrame({
                'State': list(stats['state_amounts'].keys()),
                'Amount': list(stats['state_amounts'].values())
            })
            
            fig_bar = go.Figure(data=[go.Bar(
                x=state_df['State'],
                y=state_df['Amount'],
                marker=dict(color=[STATE_COLORS.get(state, '#6b7280') for state in state_df['State']])
            )])
            fig_bar.update_layout(
                title="Amount by State",
                xaxis_title="State",
                yaxis_title="Amount (Rs)",
                height=400
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Raw data view
        with st.expander("📋 View Raw Data"):
            merchant_data = df[df['Merchant ID'] == selected_merchant]
            st.dataframe(merchant_data, use_container_width=True)
    
    else:
        st.error("❌ No valid data found in uploaded files")

else:
    # Instructions
    st.info("""
    ### 📝 Instructions:
    
    1. **Upload Files**: Click the upload button and select Excel or CSV files
    2. **Required Columns** (only these will be kept, others removed):
        - Account
        - Merchant ID
        - Amount
        - Remit. Timestamp
        - Issue Timestamp
        - State
    
    3. **Success Calculation**: Success = Only "Remitted" state
    4. **Screenshot Feature**: Use the button to see all merchants in one view
    5. **Navigate**: Use dropdown to view individual merchant details
    
    ### 🎨 Supported States:
    - Remitted (Success) ✅
    - Published
    - Rejected
    - On hold
    - Stuck
    - In review
    - In process
    - Aml review
    - No config
    """)