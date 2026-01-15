import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import io

# Page configuration
st.set_page_config(
    page_title="Ghana School Timetable Generator",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Performance optimization: cache expensive operations
@st.cache_data
def get_default_periods():
    """Generate default periods (cached for performance)"""
    default_periods = []
    start_time = datetime.strptime("7:30 AM", "%I:%M %p")
    for i in range(8):
        end_time = start_time + timedelta(minutes=45)
        period_name = f"Period {i+1}"
        time_range = f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
        default_periods.append({
            'name': period_name,
            'time_range': time_range,
            'start': start_time.strftime('%I:%M %p'),
            'end': end_time.strftime('%I:%M %p')
        })
        start_time = end_time
    return default_periods

# Custom CSS for printable style
st.markdown("""
<style>
    .timetable-container {
        background-color: white;
        padding: 20px;
        border: 2px solid #333;
        margin: 20px 0;
    }
    .school-name {
        font-size: 28px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 20px;
        color: #1a1a1a;
    }
    .timetable-table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
    }
    .timetable-table th, .timetable-table td {
        border: 1px solid #333;
        padding: 12px;
        text-align: center;
        background-color: white;
    }
    .timetable-table th {
        background-color: #f0f0f0;
        font-weight: bold;
    }
    .period-header {
        background-color: #e8e8e8;
        font-weight: bold;
    }
    @media print {
        .no-print {
            display: none;
        }
        .timetable-container {
            border: none;
            padding: 0;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    if 'school_name' not in st.session_state:
        st.session_state.school_name = "Cape Coast Secondary"
    
    if 'days' not in st.session_state:
        st.session_state.days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    if 'closing_time' not in st.session_state:
        st.session_state.closing_time = "3:00 PM"
    
    if 'periods' not in st.session_state:
        # Default: 8 periods starting at 7:30 AM, 45 minutes each (using cached function)
        st.session_state.periods = get_default_periods()
    
    if 'subjects' not in st.session_state:
        st.session_state.subjects = {
            'Math': {'hours_per_week': 4, 'no_clash': False},
            'English': {'hours_per_week': 5, 'no_clash': False},
            'Science': {'hours_per_week': 4, 'no_clash': False},
            'Social Studies': {'hours_per_week': 3, 'no_clash': False},
            'ICT': {'hours_per_week': 2, 'no_clash': False}
        }
    
    if 'non_negotiables' not in st.session_state:
        st.session_state.non_negotiables = []
    
    if 'timetable_data' not in st.session_state:
        st.session_state.timetable_data = None
    
    if 'filled_timetable' not in st.session_state:
        st.session_state.filled_timetable = {}
    
    if 'custom_items' not in st.session_state:
        st.session_state.custom_items = []

init_session_state()

# Helper functions
def parse_time(time_str):
    """Parse time string to datetime object"""
    try:
        return datetime.strptime(time_str, "%I:%M %p")
    except:
        return None

def generate_timetable():
    """Generate blank timetable grid"""
    days = st.session_state.days
    periods = st.session_state.periods
    
    # Create DataFrame with days as rows and periods as columns
    data = {}
    for period in periods:
        data[period['name']] = ['' for _ in days]
    
    # Add closing column
    data['Closing'] = [st.session_state.closing_time for _ in days]
    
    df = pd.DataFrame(data, index=days)
    df.index.name = 'Days'
    
    return df

def check_clashes(filled_data):
    """Check for clashes in filled timetable"""
    clashes = []
    
    # Check for same subject in overlapping periods (if time ranges overlap)
    # For now, check if same subject appears multiple times on same day
    for day in st.session_state.days:
        day_assignments = {}
        for period_idx, period in enumerate(st.session_state.periods):
            key = f"{day}_{period_idx}"
            if key in filled_data and filled_data[key]:
                subject = filled_data[key]
                # Only check clashes for actual subjects, not custom text
                if subject in st.session_state.subjects:
                    if subject in day_assignments:
                        clashes.append(f"Subject '{subject}' appears multiple times on {day}")
                    day_assignments[subject] = period['name']
    
    # Check weekly hours (only for subjects, not custom text)
    subject_hours = {}
    for day in st.session_state.days:
        for period_idx in range(len(st.session_state.periods)):
            key = f"{day}_{period_idx}"
            if key in filled_data and filled_data[key]:
                subject = filled_data[key]
                # Only track hours for actual subjects
                if subject in st.session_state.subjects:
                    if subject not in subject_hours:
                        subject_hours[subject] = 0
                    subject_hours[subject] += 1
    
    warnings = []
    for subject, hours in subject_hours.items():
        if subject in st.session_state.subjects:
            max_hours = st.session_state.subjects[subject]['hours_per_week']
            if hours > max_hours:
                warnings.append(f"Subject '{subject}' exceeds weekly hours: {hours}/{max_hours}")
    
    return clashes, warnings

def export_to_csv(df):
    """Export DataFrame to CSV"""
    return df.to_csv(index=True)

def export_to_json():
    """Export all settings to JSON"""
    data = {
        'school_name': st.session_state.school_name,
        'days': st.session_state.days,
        'closing_time': st.session_state.closing_time,
        'periods': st.session_state.periods,
        'subjects': st.session_state.subjects,
        'non_negotiables': st.session_state.non_negotiables,
        'filled_timetable': st.session_state.filled_timetable,
        'custom_items': st.session_state.custom_items
    }
    return json.dumps(data, indent=2)

# Main app
st.title("📅 Ghana School Timetable Generator")
st.markdown("**By Samuel Nhyira Cann**")
st.markdown("---")

# Tabs
tab1, tab2, tab3 = st.tabs(["Settings", "Generate Timetable", "Preview & Export"])

# TAB 1: SETTINGS
with tab1:
    st.header("School Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Basic Settings")
        school_name = st.text_input("School Name", value=st.session_state.school_name)
        st.session_state.school_name = school_name
        
        closing_time = st.text_input("Closing Time (e.g., 3:00 PM)", value=st.session_state.closing_time)
        st.session_state.closing_time = closing_time
    
    with col2:
        st.subheader("Days of Week")
        all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        selected_days = st.multiselect(
            "Select Days",
            options=all_days,
            default=st.session_state.days
        )
        if selected_days:
            st.session_state.days = selected_days
        
        custom_day = st.text_input("Add Custom Day (optional)", placeholder="e.g., Special Day")
        if custom_day and st.button("Add Custom Day"):
            if custom_day not in st.session_state.days:
                st.session_state.days.append(custom_day)
                st.rerun()
    
    st.markdown("---")
    st.subheader("Periods Configuration")
    
    # Periods management
    periods_to_remove = []
    for idx, period in enumerate(st.session_state.periods):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        with col1:
            period_name = st.text_input(f"Period {idx+1} Name", value=period['name'], key=f"period_name_{idx}")
        with col2:
            start_time = st.text_input(f"Start Time", value=period['start'], key=f"start_{idx}", placeholder="7:30 AM")
        with col3:
            end_time = st.text_input(f"End Time", value=period['end'], key=f"end_{idx}", placeholder="8:15 AM")
        with col4:
            if st.button("Remove", key=f"remove_{idx}"):
                periods_to_remove.append(idx)
        
        if period_name != period['name'] or start_time != period['start'] or end_time != period['end']:
            st.session_state.periods[idx]['name'] = period_name
            st.session_state.periods[idx]['start'] = start_time
            st.session_state.periods[idx]['end'] = end_time
            st.session_state.periods[idx]['time_range'] = f"{start_time} - {end_time}"
    
    # Remove periods
    for idx in sorted(periods_to_remove, reverse=True):
        st.session_state.periods.pop(idx)
        st.rerun()
    
    # Add new period
    if st.button("➕ Add New Period") and len(st.session_state.periods) < 10:
        last_period = st.session_state.periods[-1] if st.session_state.periods else None
        if last_period:
            last_end = parse_time(last_period['end'])
            if last_end:
                new_start = last_end
                new_end = last_end + timedelta(minutes=45)
                new_period = {
                    'name': f"Period {len(st.session_state.periods) + 1}",
                    'time_range': f"{new_start.strftime('%I:%M %p')} - {new_end.strftime('%I:%M %p')}",
                    'start': new_start.strftime('%I:%M %p'),
                    'end': new_end.strftime('%I:%M %p')
                }
            else:
                new_period = {
                    'name': f"Period {len(st.session_state.periods) + 1}",
                    'time_range': "8:00 AM - 8:45 AM",
                    'start': "8:00 AM",
                    'end': "8:45 AM"
                }
        else:
            new_period = {
                'name': "Period 1",
                'time_range': "7:30 AM - 8:15 AM",
                'start': "7:30 AM",
                'end': "8:15 AM"
            }
        st.session_state.periods.append(new_period)
        st.rerun()
    
    st.markdown("---")
    st.subheader("Subjects Management")
    
    # Display existing subjects
    subjects_to_remove = []
    for subject_name, subject_data in list(st.session_state.subjects.items()):
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        with col1:
            st.text_input("Subject", value=subject_name, key=f"subject_display_{subject_name}", disabled=True)
        with col2:
            hours = st.number_input("Hours/Week", min_value=1, max_value=20, value=subject_data['hours_per_week'], key=f"hours_{subject_name}")
            st.session_state.subjects[subject_name]['hours_per_week'] = hours
        with col3:
            no_clash = st.checkbox("No Clash", value=subject_data['no_clash'], key=f"noclash_{subject_name}")
            st.session_state.subjects[subject_name]['no_clash'] = no_clash
        with col4:
            if st.button("Remove", key=f"remove_subject_{subject_name}"):
                subjects_to_remove.append(subject_name)
    
    for subject in subjects_to_remove:
        del st.session_state.subjects[subject]
        if subject in st.session_state.filled_timetable:
            # Remove from filled timetable
            keys_to_remove = [k for k in st.session_state.filled_timetable.keys() if st.session_state.filled_timetable[k] == subject]
            for k in keys_to_remove:
                del st.session_state.filled_timetable[k]
        st.rerun()
    
    # Add new subject
    col1, col2 = st.columns([3, 1])
    with col1:
        new_subject = st.text_input("New Subject Name", placeholder="e.g., Physical Education")
    with col2:
        new_hours = st.number_input("Hours/Week", min_value=1, max_value=20, value=3, key="new_subject_hours")
    
    if st.button("➕ Add Subject") and new_subject:
        if new_subject not in st.session_state.subjects:
            st.session_state.subjects[new_subject] = {
                'hours_per_week': new_hours,
                'no_clash': False
            }
            st.rerun()
        else:
            st.warning(f"Subject '{new_subject}' already exists")
    
    st.markdown("---")
    st.subheader("Non-Negotiables / Fixed Items")
    st.caption("Set fixed items like 'P.E', 'Assembly', or any subject at specific times")
    
    for idx, fixed in enumerate(st.session_state.non_negotiables):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
        with col1:
            day = st.selectbox("Day", st.session_state.days, index=st.session_state.days.index(fixed['day']) if fixed['day'] in st.session_state.days else 0, key=f"fixed_day_{idx}")
        with col2:
            period_names = [p['name'] for p in st.session_state.periods]
            period_idx = period_names.index(fixed['period']) if fixed['period'] in period_names else 0
            period = st.selectbox("Period", period_names, index=period_idx, key=f"fixed_period_{idx}")
        with col3:
            # Allow custom text or subject selection
            is_custom = fixed.get('is_custom', False)
            if is_custom:
                custom_text = st.text_input("Custom Text", value=fixed.get('text', ''), key=f"fixed_custom_{idx}", placeholder="e.g., P.E, Assembly")
                st.session_state.non_negotiables[idx]['text'] = custom_text
            else:
                subject = st.selectbox("Subject", list(st.session_state.subjects.keys()), 
                                     index=list(st.session_state.subjects.keys()).index(fixed['subject']) if fixed['subject'] in st.session_state.subjects else 0,
                                     key=f"fixed_subject_{idx}")
                st.session_state.non_negotiables[idx]['subject'] = subject
        with col4:
            use_custom = st.checkbox("Custom Text", value=is_custom, key=f"fixed_custom_toggle_{idx}")
            st.session_state.non_negotiables[idx]['is_custom'] = use_custom
        with col5:
            if st.button("Remove", key=f"remove_fixed_{idx}"):
                st.session_state.non_negotiables.pop(idx)
                st.rerun()
        
        st.session_state.non_negotiables[idx]['day'] = day
        st.session_state.non_negotiables[idx]['period'] = period
    
    # Add new fixed item
    st.markdown("**Add New Fixed Item:**")
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        new_fixed_day = st.selectbox("Day", st.session_state.days, key="new_fixed_day")
    with col2:
        new_fixed_period = st.selectbox("Period", [p['name'] for p in st.session_state.periods], key="new_fixed_period")
    with col3:
        use_custom_new = st.checkbox("Use Custom Text", key="new_fixed_use_custom")
        if use_custom_new:
            new_fixed_text = st.text_input("Custom Text", key="new_fixed_text", placeholder="e.g., P.E, Assembly")
        else:
            new_fixed_subject = st.selectbox("Subject", list(st.session_state.subjects.keys()), key="new_fixed_subject")
    
    if st.button("➕ Add Fixed Item"):
        if use_custom_new and new_fixed_text:
            fixed_item = {
                'day': new_fixed_day,
                'period': new_fixed_period,
                'is_custom': True,
                'text': new_fixed_text
            }
        elif not use_custom_new:
            fixed_item = {
                'day': new_fixed_day,
                'period': new_fixed_period,
                'is_custom': False,
                'subject': new_fixed_subject
            }
        else:
            st.warning("Please enter custom text or select a subject")
            fixed_item = None
        
        if fixed_item:
            # Check if this slot is already fixed
            existing = [f for f in st.session_state.non_negotiables if f['day'] == fixed_item['day'] and f['period'] == fixed_item['period']]
            if not existing:
                st.session_state.non_negotiables.append(fixed_item)
                st.rerun()
            else:
                st.warning(f"This time slot ({new_fixed_day} - {new_fixed_period}) is already fixed")

# TAB 2: GENERATE TIMETABLE
with tab2:
    st.header("Generate Timetable")
    
    if st.button("🔄 Generate Blank Timetable", type="primary"):
        st.session_state.timetable_data = generate_timetable()
        st.success("Timetable generated successfully!")
    
    if st.session_state.timetable_data is not None:
        st.markdown("---")
        st.subheader("Blank Timetable")
        
        # Display school name
        st.markdown(f'<div class="school-name">{st.session_state.school_name}</div>', unsafe_allow_html=True)
        
        # Display timetable
        df = st.session_state.timetable_data.copy()
        
        # Create HTML table for better styling
        html_table = f"""
        <div class="timetable-container">
            <table class="timetable-table">
                <thead>
                    <tr>
                        <th class="period-header">Days</th>
        """
        
        for period in st.session_state.periods:
            html_table += f'<th class="period-header">{period["name"]}<br><small>{period["time_range"]}</small></th>'
        
        html_table += f'<th class="period-header">Closing</th>'
        html_table += "</tr></thead><tbody>"
        
        for day in st.session_state.days:
            html_table += f"<tr><td><strong>{day}</strong></td>"
            for period in st.session_state.periods:
                key = f"{day}_{st.session_state.periods.index(period)}"
                value = st.session_state.filled_timetable.get(key, "")
                html_table += f'<td>{value}</td>'
            html_table += f'<td><strong>{st.session_state.closing_time}</strong></td></tr>'
        
        html_table += "</tbody></table></div>"
        st.markdown(html_table, unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("Fill Timetable Manually")
        
        # Manual filling interface
        st.caption("💡 Tip: Use 'Custom Text' option to enter items like 'P.E', 'Assembly', etc.")
        for day in st.session_state.days:
            with st.expander(f"📅 {day}"):
                cols = st.columns(len(st.session_state.periods))
                for period_idx, period in enumerate(st.session_state.periods):
                    with cols[period_idx]:
                        key = f"{day}_{period_idx}"
                        # Check if this is a fixed item
                        is_fixed = False
                        fixed_value = None
                        fixed_is_custom = False
                        for fixed in st.session_state.non_negotiables:
                            if fixed['day'] == day and fixed['period'] == period['name']:
                                is_fixed = True
                                if fixed.get('is_custom', False):
                                    fixed_value = fixed.get('text', '')
                                    fixed_is_custom = True
                                else:
                                    fixed_value = fixed.get('subject', '')
                                break
                        
                        st.write(f"**{period['name']}**")
                        st.caption(f"{period['time_range']}")
                        
                        if is_fixed:
                            st.text_input(
                                "Value",
                                value=fixed_value,
                                key=f"{key}_fixed",
                                disabled=True
                            )
                            st.caption("🔒 Fixed")
                            # Store in filled_timetable for display
                            st.session_state.filled_timetable[key] = fixed_value
                        else:
                            # Determine if current value is custom or subject
                            current_value = st.session_state.filled_timetable.get(key, "")
                            is_current_custom = current_value and current_value not in st.session_state.subjects
                            
                            # Toggle between subject dropdown and custom text
                            use_custom = st.checkbox("Custom Text", key=f"{key}_custom_toggle", value=is_current_custom)
                            
                            if use_custom:
                                # Show custom text input
                                custom_text = st.text_input(
                                    "Enter text (e.g., P.E, Assembly)",
                                    value=current_value if is_current_custom else "",
                                    key=f"{key}_custom",
                                    placeholder="P.E, Assembly, etc."
                                )
                                if custom_text:
                                    st.session_state.filled_timetable[key] = custom_text
                                elif key in st.session_state.filled_timetable:
                                    # Only clear if it was custom text
                                    if is_current_custom:
                                        del st.session_state.filled_timetable[key]
                            else:
                                # Show subject dropdown
                                options = [""] + list(st.session_state.subjects.keys())
                                # If current value is a subject, use it; otherwise default to empty
                                index = options.index(current_value) if current_value in options else 0
                                selected = st.selectbox(
                                    "Select Subject",
                                    options=options,
                                    index=index,
                                    key=f"{key}_subject"
                                )
                                if selected:
                                    st.session_state.filled_timetable[key] = selected
                                elif key in st.session_state.filled_timetable:
                                    # Only clear if it was a subject
                                    if not is_current_custom:
                                        del st.session_state.filled_timetable[key]
        
        # Check for clashes
        if st.button("🔍 Check for Clashes"):
            clashes, warnings = check_clashes(st.session_state.filled_timetable)
            if clashes:
                st.error("**Clashes Found:**")
                for clash in clashes:
                    st.error(f"⚠️ {clash}")
            else:
                st.success("✅ No clashes detected!")
            
            if warnings:
                st.warning("**Warnings:**")
                for warning in warnings:
                    st.warning(f"⚠️ {warning}")

# TAB 3: PREVIEW & EXPORT
with tab3:
    st.header("Preview & Export")
    
    if st.session_state.timetable_data is None:
        st.info("Please generate a timetable first in the 'Generate Timetable' tab.")
    else:
        st.subheader("Timetable Preview")
        
        # Display school name
        st.markdown(f'<div class="school-name">{st.session_state.school_name}</div>', unsafe_allow_html=True)
        
        # Create filled DataFrame
        df_filled = st.session_state.timetable_data.copy()
        for day in st.session_state.days:
            for period_idx, period in enumerate(st.session_state.periods):
                key = f"{day}_{period_idx}"
                if key in st.session_state.filled_timetable:
                    df_filled.loc[day, period['name']] = st.session_state.filled_timetable[key]
        
        # Display as DataFrame
        st.dataframe(df_filled, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Export Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            csv_data = export_to_csv(df_filled)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"{st.session_state.school_name.replace(' ', '_')}_timetable.csv",
                mime="text/csv"
            )
        
        with col2:
            json_data = export_to_json()
            st.download_button(
                label="📥 Download JSON (Settings)",
                data=json_data,
                file_name=f"{st.session_state.school_name.replace(' ', '_')}_settings.json",
                mime="application/json"
            )
        
        with col3:
            if st.button("🖨️ Print View"):
                st.info("Use your browser's print function (Ctrl+P) to print the timetable. The print view will hide navigation elements.")
        
        st.markdown("---")
        st.subheader("Summary")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Configuration:**")
            st.write(f"- School: {st.session_state.school_name}")
            st.write(f"- Days: {', '.join(st.session_state.days)}")
            st.write(f"- Periods: {len(st.session_state.periods)}")
            st.write(f"- Closing Time: {st.session_state.closing_time}")
            st.write(f"- Subjects: {len(st.session_state.subjects)}")
            st.write(f"- Fixed Items: {len(st.session_state.non_negotiables)}")
        
        with col2:
            st.write("**Subjects & Hours:**")
            for subject, data in st.session_state.subjects.items():
                hours_used = sum(1 for v in st.session_state.filled_timetable.values() if v == subject)
                st.write(f"- {subject}: {hours_used}/{data['hours_per_week']} hours")

# Sidebar info
with st.sidebar:
    st.header("ℹ️ About")
    st.write("""
    This app helps Ghanaian schools create customizable timetables.
    
    **Features:**
    - Customizable days and periods
    - Subject management with weekly hours
    - Clash detection
    - Fixed/non-negotiable items
    - Export to CSV/JSON
    - Printable format
    """)
    
    st.markdown("---")
    st.write("**Quick Tips:**")
    st.write("1. Configure settings first")
    st.write("2. Generate blank timetable")
    st.write("3. Fill manually or use auto-fill")
    st.write("4. Check for clashes")
    st.write("5. Export when ready")
