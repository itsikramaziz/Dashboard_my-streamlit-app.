import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io
from datetime import datetime
import tempfile
import os

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

def get_merchant_date_range(df, merchant_id):
    """Get date range for a specific merchant from Issue Timestamp column"""
    merchant_data = df[df['Merchant ID'] == merchant_id].copy()
    
    if len(merchant_data) == 0:
        return None, None
    
    # Use only Issue Timestamp column
    if 'Issue Timestamp' not in merchant_data.columns:
        return None, None
    
    try:
        parsed_dates = pd.to_datetime(merchant_data['Issue Timestamp'], errors='coerce')
        valid_dates = parsed_dates.dropna()
        
        if len(valid_dates) == 0:
            return None, None
        
        min_date = valid_dates.min()
        max_date = valid_dates.max()
        
        return min_date, max_date
    except:
        return None, None

def format_date_range(min_date, max_date):
    """Format date range for display"""
    if min_date is None or max_date is None:
        return "N/A"
    
    min_str = pd.Timestamp(min_date).strftime('%d-%b-%Y')
    max_str = pd.Timestamp(max_date).strftime('%d-%b-%Y')
    
    if min_str == max_str:
        return min_str
    return f"{min_str} to {max_str}"

def format_currency(amount):
    """Format amount as Pakistani currency"""
    return f"Rs {amount:,.0f}"

def generate_pdf_report(df, merchants):
    """Generate a professional one-page PDF report of all merchants"""
    
    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(letter), topMargin=0.3*inch, bottomMargin=0.3*inch)
    
    # Container for report elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    # Title
    elements.append(Paragraph("🏦 SIMPAISA SR DASHBOARD - MERCHANTS REPORT", title_style))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 0.15*inch))
    
    # Overall Summary Table
    total_merchants = len(merchants)
    total_txns = len(df)
    success_txns = len(df[df['State'] == 'Remitted'])
    overall_sr = (success_txns / total_txns * 100) if total_txns > 0 else 0
    total_amount = df['Amount'].sum()
    success_amount = df[df['State'] == 'Remitted']['Amount'].sum()
    
    summary_data = [
        ['Metric', 'Value'],
        ['Total Merchants', str(total_merchants)],
        ['Total Transactions', f"{total_txns:,}"],
        ['Overall Success Rate', f"{overall_sr:.2f}%"],
        ['Total Amount', f"Rs {total_amount:,.0f}"],
        ['Remitted Amount', f"Rs {success_amount:,.0f}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Merchants Details Table
    merchant_table_data = [
        ['Merchant ID', 'Date Range', 'Total Txns', 'Success Txns', 'SR %', 'Total Amount', 'Remitted Amount', 'Top State']
    ]
    
    for merchant in sorted(merchants):
        stats = calculate_merchant_stats(df, merchant)
        min_date, max_date = get_merchant_date_range(df, merchant)
        date_range_str = format_date_range(min_date, max_date)
        
        # Get top state - handle empty state_counts
        if stats['state_counts']:
            top_state = max(stats['state_counts'].items(), key=lambda x: x[1])[0]
        else:
            top_state = 'N/A'
        
        merchant_table_data.append([
            str(merchant)[:18],
            date_range_str,
            str(stats['total_txns']),
            str(stats['success_txns']),
            f"{stats['success_rate']:.1f}%",
            f"Rs {stats['total_amount']:,.0f}",
            f"Rs {stats['success_amount']:,.0f}",
            top_state
        ])
    
    merchant_table = Table(merchant_table_data, colWidths=[0.95*inch, 1.25*inch, 0.75*inch, 0.85*inch, 0.6*inch, 1.0*inch, 1.0*inch, 0.85*inch])
    merchant_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    
    elements.append(Paragraph("📊 Merchants Detailed Report", ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )))
    elements.append(merchant_table)
    elements.append(Spacer(1, 0.1*inch))
    
    # Footer
    footer_text = "Confidential - For Internal Use Only | Simpaisa SR Dashboard"
    elements.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#9ca3af'),
        alignment=TA_CENTER
    )))
    
    # Build PDF
    doc.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer

def send_report_via_email(pdf_buffer, filename):
    """Send report via email using SMTP"""
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email.mime.text import MIMEText
        from email import encoders
        
        # Read credentials from config file
        config_path = os.path.join(os.path.dirname(__file__), 'config.txt')
        
        if not os.path.exists(config_path):
            st.error("❌ config.txt not found! Create it with SENDER_EMAIL and APP_PASSWORD")
            return False, "Config file missing"
        
        # Parse config file
        config = {}
        with open(config_path, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config[key.strip()] = value.strip()
        
        sender_email = config.get('SENDER_EMAIL')
        password = config.get('APP_PASSWORD')
        
        if not sender_email or not password:
            st.error("❌ SENDER_EMAIL or APP_PASSWORD missing in config.txt")
            return False, "Missing credentials in config"
        
        recipient_email = "maaz.haider@simpaisa.com"
        cc_email = "naim.majeed@simpaisa.com"
        
        smtp_server = "smtp.office365.com"
        smtp_port = 587
        
        # Create message
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Cc'] = cc_email
        message['Subject'] = f'Simpaisa SR Dashboard Report - {datetime.now().strftime("%d-%b-%Y")}'
        
        # Email body
        body = f"""
Dear Team,

Please find attached the Simpaisa SR Dashboard report generated on {datetime.now().strftime("%B %d, %Y at %H:%M")}.

This report contains comprehensive merchant transaction data including success rates, amounts, and date ranges.

Best regards,
Simpaisa Dashboard System
"""
        message.attach(MIMEText(body, 'plain'))
        
        # Attach PDF
        pdf_buffer.seek(0)
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_buffer.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename= {filename}')
        message.attach(part)
        
        try:
            # Create SMTP session
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, password)
            
            # Send email
            all_recipients = [recipient_email, cc_email]
            server.sendmail(sender_email, all_recipients, message.as_string())
            server.quit()
            
            return True, f"✅ Email sent successfully to {recipient_email} and {cc_email}!"
            
        except smtplib.SMTPAuthenticationError:
            st.error(f"❌ Authentication Error: Wrong email or app password in config.txt")
            return False, "Authentication failed"
            
        except smtplib.SMTPException as e:
            return False, f"❌ SMTP error: {str(e)}"
            
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# Title
st.title("🏦 Simpaisa SR Dashboard")
st.markdown("---")

# Test email configuration on startup



import smtplib
import traceback

def send_email_with_logging(sender_email, app_password, recipient_email, subject, body):
    """Send email with detailed error logging"""
    
    print("\n" + "="*60)
    print("EMAIL SENDING ATTEMPT - DEBUG INFO")
    print("="*60)
    print(f"Sender: {sender_email}")
    print(f"Recipient: {recipient_email}")
    print(f"Password length: {len(app_password)}")
    print(f"Subject: {subject}")
    print("="*60 + "\n")
    
    try:
        # Create server
        print("Step 1: Creating SMTP server connection...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        print("✓ Server connection created")
        
        # Start TLS
        print("Step 2: Starting TLS encryption...")
        server.starttls()
        print("✓ TLS encryption started")
        
        # Login
        print("Step 3: Attempting login...")
        print(f"   Email: {sender_email}")
        print(f"   Password: {app_password[:4]}...{app_password[-4:]}")
        server.login(sender_email, app_password)
        print("✓ Login successful")
        
        # Send email
        print("Step 4: Sending email...")
        server.send_message(msg)
        print("✓ Email sent successfully")
        
        server.quit()
        return True, "Email sent successfully"
        
    except smtplib.SMTPAuthenticationError as e:
        error_details = f"""
{'='*60}
SMTP AUTHENTICATION ERROR
{'='*60}
Error Type: SMTPAuthenticationError
Error Code: {e.smtp_code if hasattr(e, 'smtp_code') else 'N/A'}
Error Message: {e.smtp_error.decode() if hasattr(e, 'smtp_error') else str(e)}

Configuration:
- Email: {sender_email}
- Password Length: {len(app_password)} chars
- Password Preview: {app_password[:4]}...{app_password[-4:]}

Full Exception:
{str(e)}

Traceback:
{traceback.format_exc()}
{'='*60}
        """
        
        print(error_details)
        st.error("❌ Authentication Error")
        st.code(error_details)
        
        return False, f"Authentication failed: {str(e)}"
        
    except smtplib.SMTPException as e:
        error_details = f"""
{'='*60}
SMTP ERROR
{'='*60}
Error Type: {type(e).__name__}
Error Message: {str(e)}

Traceback:
{traceback.format_exc()}
{'='*60}
        """
        
        print(error_details)
        st.error(f"❌ SMTP Error: {type(e).__name__}")
        st.code(error_details)
        
        return False, f"SMTP Error: {str(e)}"
        
    except Exception as e:
        error_details = f"""
{'='*60}
UNEXPECTED ERROR
{'='*60}
Error Type: {type(e).__name__}
Error Message: {str(e)}

Traceback:
{traceback.format_exc()}
{'='*60}
        """
        
        print(error_details)
        st.error(f"❌ Unexpected Error: {type(e).__name__}")
        st.code(error_details)
        
        return False, f"Error: {str(e)}"

#---------------------------TESTING LOGS-----------

@st.cache_data

def check_email_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.txt')
    if os.path.exists(config_path):
        return "✅ Email configured"
    return "❌ Email NOT configured"

# Email configuration status
email_config_status = check_email_config()

# Warning for email configuration
if email_config_status == "❌ Email NOT configured":
    st.warning("""
    ⚠️ **Email not configured** 
    
    Create a file named `config.txt` in the same folder as this script with:
    ```
    SENDER_EMAIL=ikram.aziz@simpaisa.com
    APP_PASSWORD=your_app_password_here
    ```
    """)

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
            # Create merchant display with date range
            merchant_options = []
            for merchant in merchants:
                min_date, max_date = get_merchant_date_range(df, merchant)
                date_range = format_date_range(min_date, max_date)
                merchant_options.append((merchant, date_range))
            
            selected_merchant = st.selectbox(
                "Choose Merchant",
                [m[0] for m in merchant_options],
                format_func=lambda x: f"{x} | {next(m[1] for m in merchant_options if m[0] == x)}"
            )
        
        # Calculate merchant stats
        stats = calculate_merchant_stats(df, selected_merchant)
        min_date, max_date = get_merchant_date_range(df, selected_merchant)
        date_range_display = format_date_range(min_date, max_date)
        
        st.markdown(f"## Merchant: **{selected_merchant}**")
        st.markdown(f"<p style='color: #6b7280; margin-top: -15px;'>📅 <b>Date Range:</b> {date_range_display}</p>", unsafe_allow_html=True)
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
        
        # Add date range info box after KPI Cards
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div style='background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 12px; border-radius: 6px;'>
                <p style='margin: 0; color: #1e40af; font-size: 0.85rem;'><b>📅 Transaction Period</b></p>
                <p style='margin: 5px 0 0 0; color: #1f2937; font-weight: bold;'>{date_range_display}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            if min_date:
                days_span = (pd.Timestamp(max_date) - pd.Timestamp(min_date)).days + 1
                st.markdown(f"""
                <div style='background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; border-radius: 6px;'>
                    <p style='margin: 0; color: #92400e; font-size: 0.85rem;'><b>⏱️ Duration</b></p>
                    <p style='margin: 5px 0 0 0; color: #1f2937; font-weight: bold;'>{days_span} days</p>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            if min_date:
                daily_avg = stats['total_txns'] / max(1, (pd.Timestamp(max_date) - pd.Timestamp(min_date)).days + 1)
                st.markdown(f"""
                <div style='background: #dbeafe; border-left: 4px solid #06b6d4; padding: 12px; border-radius: 6px;'>
                    <p style='margin: 0; color: #0c4a6e; font-size: 0.85rem;'><b>📊 Daily Average</b></p>
                    <p style='margin: 5px 0 0 0; color: #1f2937; font-weight: bold;'>{daily_avg:.1f} txns/day</p>
                </div>
                """, unsafe_allow_html=True)
        
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
        
        st.markdown("---")
        
        # 📄 GENERATE & DOWNLOAD REPORT SECTION
        st.markdown("### 📄 Generate Report")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            **Create a professional one-page PDF report** containing all merchants' data with key metrics and visualizations.
            Perfect for sharing with your manager or stakeholders.
            """)
        
        with col2:
            if st.button("📥 Generate & Download Report", use_container_width=True, type="primary", key="generate_report"):
                with st.spinner("Generating PDF report..."):
                    try:
                        pdf_buffer = generate_pdf_report(df, merchants)
                        
                        # Prepare download
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"Simpaisa_SR_Report_{timestamp}.pdf"
                        
                        st.download_button(
                            label="✅ Download PDF Report",
                            data=pdf_buffer,
                            file_name=filename,
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                        st.success(f"✅ Report generated successfully!")
                        
                        # Send email
                        st.info("📧 Sending email with report...")
                        pdf_buffer.seek(0)
                        success, message = send_report_via_email(pdf_buffer, filename)
                        
                        if success:
                            st.success(message)
                            st.balloons()
                        else:
                            st.warning(message)
                        
                    except Exception as e:
                        st.error(f"❌ Error generating report: {str(e)}")

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