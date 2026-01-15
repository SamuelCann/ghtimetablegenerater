import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import io
import traceback

# Page configuration with error handling
try:
    st.set_page_config(
        page_title="Ghana Timetable Generator",
        page_icon="📅",
        layout="wide",
        initial_sidebar_state="expanded"
    )
except Exception:
    pass  # Already set

# Custom CSS with color support
st.markdown("""
<style>
    .timetable-container {
        background-color: white;
        padding: 20px;
        border: 2px solid #333;
        margin: 20px 0;
        overflow-x: auto;
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
        padding: 8px;
        text-align: center;
        min-width: 100px;
    }
    .timetable-table th {
        background-color: #f0f0f0;
        font-weight: bold;
        position: sticky;
        top: 0;
        z-index: 10;
    }
    .period-header {
        background-color: #e8e8e8;
        font-weight: bold;
    }
    .fixed-event {
        font-weight: bold;
        text-align: center;
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
    .stAlert {
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state with all required variables
def init_session_state():
    """Initialize all session state variables with error handling"""
    try:
        defaults = {
            'school_name': "Cape Coast Secondary",
            'classes': ['JHS1', 'JHS2', 'JHS3'],
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            'subjects': {
                'English': {'hours_per_week': 5, 'teacher': '', 'single_teacher': False, 'no_clash': False},
                'Mathematics': {'hours_per_week': 5, 'teacher': '', 'single_teacher': False, 'no_clash': False},
                'Integrated Science': {'hours_per_week': 4, 'teacher': '', 'single_teacher': False, 'no_clash': False},
                'Social Studies': {'hours_per_week': 3, 'teacher': '', 'single_teacher': False, 'no_clash': False},
                'ICT': {'hours_per_week': 2, 'teacher': '', 'single_teacher': False, 'no_clash': False}
            },
            'teachers': [],
            'time_slots': {},  # {day: [{'start': '7:30 AM', 'end': '8:30 AM', 'name': 'Period 1'}, ...]}
            'fixed_events': [],  # Events spanning multiple days
            'fixed_assignments': [],  # Non-negotiable assignments
            'timetable_data': {},  # {class: (DataFrame, all_slots)}
            'timetable_colors': {},  # {class: {slot_key: color}}
            'other_timetable': None,  # Uploaded timetable for clash checking
            'generation_status': {}
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    except Exception as e:
        st.error(f"Error initializing session state: {str(e)}")

# Initialize with error handling
try:
    init_session_state()
except Exception:
    pass  # Continue even if initialization fails

# Helper functions
def parse_time(time_str):
    """Parse time string to datetime object"""
    try:
        return datetime.strptime(time_str.strip(), "%I:%M %p")
    except:
        try:
            return datetime.strptime(time_str.strip(), "%H:%M")
        except:
            return None

def time_to_minutes(time_str):
    """Convert time string to minutes since midnight"""
    dt = parse_time(time_str)
    if dt:
        return dt.hour * 60 + dt.minute
    return None

def minutes_to_time(minutes):
    """Convert minutes since midnight to time string"""
    hours = minutes // 60
    mins = minutes % 60
    period = "AM" if hours < 12 else "PM"
    if hours == 0:
        hours = 12
    elif hours > 12:
        hours -= 12
    return f"{hours}:{mins:02d} {period}"

def check_time_overlap(start1, end1, start2, end2):
    """Check if two time ranges overlap"""
    s1 = time_to_minutes(start1)
    e1 = time_to_minutes(end1)
    s2 = time_to_minutes(start2)
    e2 = time_to_minutes(end2)
    if None in [s1, e1, s2, e2]:
        return False
    return not (e1 <= s2 or e2 <= s1)

def validate_time_slots():
    """Validate time slots for overlaps and errors"""
    errors = []
    warnings = []
    
    for day in st.session_state.days:
        if day not in st.session_state.time_slots:
            continue
        slots = st.session_state.time_slots[day]
        for i, slot1 in enumerate(slots):
            for j, slot2 in enumerate(slots):
                if i != j:
                    if check_time_overlap(slot1['start'], slot1['end'], slot2['start'], slot2['end']):
                        errors.append(f"{day}: Overlapping time slots: {slot1['name']} and {slot2['name']}")
    
    return errors, warnings

def generate_timetable_grid(class_name, days, time_slots_dict):
    """Generate blank timetable grid for a class with size limits"""
    # Collect all unique time slots across days
    all_slots = []
    slot_keys = {}  # Map (day, start, end) to slot name
    
    # Limit total slots to prevent memory issues
    max_slots = 100
    
    for day in days:
        if day in time_slots_dict and len(all_slots) < max_slots:
            for slot in time_slots_dict[day]:
                if len(all_slots) >= max_slots:
                    break
                key = (day, slot['start'], slot['end'])
                if key not in slot_keys:
                    slot_keys[key] = slot['name']
                    all_slots.append({
                        'day': day,
                        'start': slot['start'],
                        'end': slot['end'],
                        'name': slot['name']
                    })
    
    if not all_slots:
        raise ValueError("No time slots defined. Please add time slots in the 'Time Slots' tab.")
    
    # Create DataFrame with time slots as rows and days as columns
    data = {}
    for day in days:
        data[day] = ['' for _ in all_slots]
    
    df = pd.DataFrame(data, index=[f"{s['name']} ({s['start']}-{s['end']})" for s in all_slots])
    df.index.name = 'Time Slots'
    
    return df, all_slots

def apply_fixed_events(df, all_slots, fixed_events):
    """Apply fixed events that span multiple days"""
    for event in fixed_events:
        if event.get('same_all_days', False):
            # Find matching time slots
            event_start = event['start_time']
            event_end = event['end_time']
            
            for idx, slot in enumerate(all_slots):
                if slot['start'] == event_start and slot['end'] == event_end:
                    # Apply to all days
                    for day in st.session_state.days:
                        df.loc[df.index[idx], day] = event['name']
                    break

def apply_fixed_assignments(df, all_slots, fixed_assignments, class_name):
    """Apply non-negotiable fixed assignments"""
    for assignment in fixed_assignments:
        if assignment.get('class') != class_name:
            continue
        
        day = assignment['day']
        start = assignment['start_time']
        end = assignment['end_time']
        subject = assignment.get('subject', '')
        teacher = assignment.get('teacher', '')
        
        # Find matching slot
        for idx, slot in enumerate(all_slots):
            if slot['day'] == day and slot['start'] == start and slot['end'] == end:
                value = subject
                if teacher:
                    value += f" ({teacher})"
                df.loc[df.index[idx], day] = value
                break

def auto_generate_subjects(df, all_slots, class_name, subjects_dict):
    """Automatically assign subjects to time slots"""
    # Count remaining hours needed per subject
    subject_hours = {}
    for subject, data in subjects_dict.items():
        hours = data.get('hours_per_week', 0)
        # Count already assigned hours
        assigned = 0
        for idx, slot in enumerate(all_slots):
            for day in st.session_state.days:
                cell_value = df.loc[df.index[idx], day]
                if subject in str(cell_value):
                    assigned += 1
        subject_hours[subject] = max(0, hours - assigned)
    
    # Round-robin assignment
    subjects_list = [s for s, h in subject_hours.items() if h > 0]
    if not subjects_list:
        return
    
    subject_idx = 0
    for idx, slot in enumerate(all_slots):
        for day in st.session_state.days:
            if df.loc[df.index[idx], day] == '':
                if subject_idx < len(subjects_list):
                    subject = subjects_list[subject_idx]
                    df.loc[df.index[idx], day] = subject
                    subject_hours[subject] -= 1
                    if subject_hours[subject] <= 0:
                        subjects_list.remove(subject)
                        if not subjects_list:
                            return
                        subject_idx = subject_idx % len(subjects_list)
                    else:
                        subject_idx = (subject_idx + 1) % len(subjects_list)

def check_teacher_clashes(timetable_data, class_name):
    """Check for teacher clashes within and across classes"""
    clashes = []
    teacher_schedule = {}  # {teacher: [(day, start, end, class, subject)]}
    
    # Check current class
    if class_name in timetable_data:
        df, all_slots = timetable_data[class_name]
        for idx, slot in enumerate(all_slots):
            for day in st.session_state.days:
                cell_value = str(df.loc[df.index[idx], day])
                if cell_value and '(' in cell_value:
                    # Extract teacher name
                    parts = cell_value.split('(')
                    if len(parts) > 1:
                        teacher = parts[1].rstrip(')').strip()
                        if teacher:
                            key = (day, slot['start'], slot['end'])
                            if teacher not in teacher_schedule:
                                teacher_schedule[teacher] = []
                            teacher_schedule[teacher].append((day, slot['start'], slot['end'], class_name, parts[0].strip()))
    
    # Check for overlaps
    for teacher, schedule in teacher_schedule.items():
        for i, (day1, start1, end1, class1, subj1) in enumerate(schedule):
            for j, (day2, start2, end2, class2, subj2) in enumerate(schedule):
                if i != j and day1 == day2:
                    if check_time_overlap(start1, end1, start2, end2):
                        clashes.append(f"Teacher '{teacher}' double-booked: {class1} {subj1} and {class2} {subj2} on {day1}")
    
    return clashes

def export_to_excel(timetable_data):
    """Export all timetables to Excel with error handling"""
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for class_name, data in timetable_data.items():
                if isinstance(data, tuple):
                    df, _ = data
                else:
                    df = data
                # Limit sheet name length
                sheet_name = class_name[:31] if len(class_name) > 31 else class_name
                df.to_excel(writer, sheet_name=sheet_name)
        return output.getvalue()
    except ImportError:
        raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")
    except Exception as e:
        raise Exception(f"Error exporting to Excel: {str(e)}")

# Main app with comprehensive error handling
try:
    # Add loading state to prevent multiple simultaneous operations
    if 'app_ready' not in st.session_state:
        st.session_state.app_ready = True
    
    if not st.session_state.app_ready:
        st.warning("App is initializing... Please wait.")
        st.stop()
    
    st.title("📅 Ghana Timetable Generator")
    st.markdown("**By Samuel Nhyira Cann**")
    st.markdown("---")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Setup", "Time Slots", "Fixed Events", "Fixed Assignments", 
        "Integrate Other Timetable", "Generate & View"
    ])
    
    # TAB 1: SETUP
    with tab1:
        st.header("School & Class Setup")
        
        col1, col2 = st.columns(2)
        with col1:
            school_name = st.text_input("School Name", value=st.session_state.school_name)
            st.session_state.school_name = school_name
        
        with col2:
            st.subheader("Classes")
            classes_input = st.text_area(
                "Enter classes (one per line)",
                value="\n".join(st.session_state.classes),
                height=100
            )
            if classes_input:
                st.session_state.classes = [c.strip() for c in classes_input.split('\n') if c.strip()]
        
        st.markdown("---")
        st.subheader("Subjects Management")
        
        # Display existing subjects
        subjects_to_remove = []
        for subject_name, subject_data in list(st.session_state.subjects.items()):
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
            with col1:
                st.text_input("Subject", value=subject_name, key=f"subj_display_{subject_name}", disabled=True)
            with col2:
                hours = st.number_input("Hours/Week", min_value=1, max_value=20, value=subject_data['hours_per_week'], key=f"hours_{subject_name}")
                st.session_state.subjects[subject_name]['hours_per_week'] = hours
            with col3:
                teacher = st.text_input("Teacher", value=subject_data.get('teacher', ''), key=f"teacher_{subject_name}")
                st.session_state.subjects[subject_name]['teacher'] = teacher
            with col4:
                single_teacher = st.checkbox("Single Teacher Only", value=subject_data.get('single_teacher', False), key=f"single_{subject_name}")
                st.session_state.subjects[subject_name]['single_teacher'] = single_teacher
            with col5:
                if st.button("Remove", key=f"remove_subj_{subject_name}"):
                    subjects_to_remove.append(subject_name)
        
        for subject in subjects_to_remove:
            del st.session_state.subjects[subject]
            if st.button("Confirm Remove", key=f"confirm_remove_{subject}"):
                st.rerun()
        
        # Add new subject
        st.markdown("**Add New Subject:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            new_subject = st.text_input("Subject Name", key="new_subject_name")
        with col2:
            new_hours = st.number_input("Hours/Week", min_value=1, max_value=20, value=3, key="new_subject_hours")
        with col3:
            new_teacher = st.text_input("Teacher", key="new_subject_teacher")
        
        if st.button("➕ Add Subject") and new_subject:
            if new_subject not in st.session_state.subjects:
                st.session_state.subjects[new_subject] = {
                    'hours_per_week': new_hours,
                    'teacher': new_teacher,
                    'single_teacher': False,
                    'no_clash': False
                }
                st.rerun()
    
    # TAB 2: TIME SLOTS
    with tab2:
        st.header("Customizable Time Periods per Day")
        st.caption("Define different time periods for each day of the week")
        
        selected_day = st.selectbox("Select Day", st.session_state.days, key="time_slot_day")
        
        if selected_day not in st.session_state.time_slots:
            st.session_state.time_slots[selected_day] = []
        
        st.subheader(f"Time Slots for {selected_day}")
        
        # Display existing slots
        slots_to_remove = []
        for idx, slot in enumerate(st.session_state.time_slots[selected_day]):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            with col1:
                name = st.text_input("Slot Name", value=slot['name'], key=f"slot_name_{selected_day}_{idx}")
            with col2:
                start = st.text_input("Start Time", value=slot['start'], key=f"slot_start_{selected_day}_{idx}", placeholder="7:30 AM")
            with col3:
                end = st.text_input("End Time", value=slot['end'], key=f"slot_end_{selected_day}_{idx}", placeholder="8:30 AM")
            with col4:
                if st.button("Remove", key=f"remove_slot_{selected_day}_{idx}"):
                    slots_to_remove.append(idx)
            
            st.session_state.time_slots[selected_day][idx] = {
                'name': name,
                'start': start,
                'end': end
            }
        
        # Remove slots
        for idx in sorted(slots_to_remove, reverse=True):
            st.session_state.time_slots[selected_day].pop(idx)
            st.rerun()
        
        # Add new slot
        col1, col2, col3 = st.columns(3)
        with col1:
            new_slot_name = st.text_input("New Slot Name", key=f"new_slot_name_{selected_day}", placeholder="Period 1")
        with col2:
            new_slot_start = st.text_input("Start Time", key=f"new_slot_start_{selected_day}", placeholder="7:30 AM")
        with col3:
            new_slot_end = st.text_input("End Time", key=f"new_slot_end_{selected_day}", placeholder="8:30 AM")
        
        if st.button("➕ Add Time Slot") and new_slot_name and new_slot_start and new_slot_end:
            st.session_state.time_slots[selected_day].append({
                'name': new_slot_name,
                'start': new_slot_start,
                'end': new_slot_end
            })
            st.rerun()
        
        # Validate
        errors, warnings = validate_time_slots()
        if errors:
            st.error("**Time Slot Errors:**")
            for error in errors:
                st.error(f"⚠️ {error}")
        if warnings:
            st.warning("**Warnings:**")
            for warning in warnings:
                st.warning(f"⚠️ {warning}")
    
    # TAB 3: FIXED EVENTS
    with tab3:
        st.header("Fixed Events Spanning Multiple Days")
        st.caption("Events like assembly that occur at the same time every day")
        
        # Display existing fixed events
        events_to_remove = []
        for idx, event in enumerate(st.session_state.fixed_events):
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
            with col1:
                name = st.text_input("Event Name", value=event['name'], key=f"event_name_{idx}")
            with col2:
                start = st.text_input("Start Time", value=event['start_time'], key=f"event_start_{idx}", placeholder="3:00 PM")
            with col3:
                end = st.text_input("End Time", value=event['end_time'], key=f"event_end_{idx}", placeholder="3:15 PM")
            with col4:
                same_all = st.checkbox("All Days", value=event.get('same_all_days', False), key=f"event_all_{idx}")
            with col5:
                if st.button("Remove", key=f"remove_event_{idx}"):
                    events_to_remove.append(idx)
            
            st.session_state.fixed_events[idx] = {
                'name': name,
                'start_time': start,
                'end_time': end,
                'same_all_days': same_all
            }
        
        for idx in sorted(events_to_remove, reverse=True):
            st.session_state.fixed_events.pop(idx)
            st.rerun()
        
        # Add new fixed event
        st.markdown("**Add New Fixed Event:**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_event_name = st.text_input("Event Name", key="new_event_name", placeholder="Assembly")
        with col2:
            new_event_start = st.text_input("Start Time", key="new_event_start", placeholder="3:00 PM")
        with col3:
            new_event_end = st.text_input("End Time", key="new_event_end", placeholder="3:15 PM")
        with col4:
            new_event_all_days = st.checkbox("Same for all days (Mon-Fri)", key="new_event_all_days")
        
        if st.button("➕ Add Fixed Event") and new_event_name and new_event_start and new_event_end:
            st.session_state.fixed_events.append({
                'name': new_event_name,
                'start_time': new_event_start,
                'end_time': new_event_end,
                'same_all_days': new_event_all_days
            })
            st.rerun()
    
    # TAB 4: FIXED ASSIGNMENTS
    with tab4:
        st.header("Non-Negotiable Fixed Assignments")
        st.caption("Part-time teachers or other fixed time constraints")
        
        # Display existing fixed assignments
        assignments_to_remove = []
        for idx, assignment in enumerate(st.session_state.fixed_assignments):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 2, 2, 2, 2, 1, 1])
            with col1:
                class_name = st.selectbox("Class", st.session_state.classes, 
                                        index=st.session_state.classes.index(assignment['class']) if assignment['class'] in st.session_state.classes else 0,
                                        key=f"fixed_class_{idx}")
            with col2:
                day = st.selectbox("Day", st.session_state.days,
                                 index=st.session_state.days.index(assignment['day']) if assignment['day'] in st.session_state.days else 0,
                                 key=f"fixed_day_{idx}")
            with col3:
                start = st.text_input("Start", value=assignment['start_time'], key=f"fixed_start_{idx}", placeholder="8:00 AM")
            with col4:
                end = st.text_input("End", value=assignment['end_time'], key=f"fixed_end_{idx}", placeholder="10:00 AM")
            with col5:
                subject = st.selectbox("Subject", [""] + list(st.session_state.subjects.keys()),
                                     index=([""] + list(st.session_state.subjects.keys())).index(assignment.get('subject', '')) if assignment.get('subject', '') in [""] + list(st.session_state.subjects.keys()) else 0,
                                     key=f"fixed_subject_{idx}")
            with col6:
                teacher = st.text_input("Teacher", value=assignment.get('teacher', ''), key=f"fixed_teacher_{idx}")
            with col7:
                if st.button("Remove", key=f"remove_fixed_{idx}"):
                    assignments_to_remove.append(idx)
            
            st.session_state.fixed_assignments[idx] = {
                'class': class_name,
                'day': day,
                'start_time': start,
                'end_time': end,
                'subject': subject,
                'teacher': teacher
            }
        
        for idx in sorted(assignments_to_remove, reverse=True):
            st.session_state.fixed_assignments.pop(idx)
            st.rerun()
        
        # Add new fixed assignment
        st.markdown("**Add New Fixed Assignment:**")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            new_fixed_class = st.selectbox("Class", st.session_state.classes, key="new_fixed_class")
        with col2:
            new_fixed_day = st.selectbox("Day", st.session_state.days, key="new_fixed_day")
        with col3:
            new_fixed_start = st.text_input("Start Time", key="new_fixed_start", placeholder="8:00 AM")
        with col4:
            new_fixed_end = st.text_input("End Time", key="new_fixed_end", placeholder="10:00 AM")
        with col5:
            new_fixed_subject = st.selectbox("Subject", [""] + list(st.session_state.subjects.keys()), key="new_fixed_subject")
        with col6:
            new_fixed_teacher = st.text_input("Teacher", key="new_fixed_teacher")
        
        if st.button("➕ Add Fixed Assignment") and new_fixed_class and new_fixed_day and new_fixed_start and new_fixed_end:
            st.session_state.fixed_assignments.append({
                'class': new_fixed_class,
                'day': new_fixed_day,
                'start_time': new_fixed_start,
                'end_time': new_fixed_end,
                'subject': new_fixed_subject,
                'teacher': new_fixed_teacher
            })
            st.rerun()
    
    # TAB 5: INTEGRATE OTHER TIMETABLE
    with tab5:
        st.header("Integrate Other Timetable")
        st.caption("Upload another timetable (CSV/Excel) to avoid teacher clashes")
        
        uploaded_file = st.file_uploader("Upload Timetable", type=['csv', 'xlsx', 'xls'])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_other = pd.read_csv(uploaded_file)
                else:
                    df_other = pd.read_excel(uploaded_file)
                
                st.session_state.other_timetable = df_other
                st.success("Timetable uploaded successfully!")
                st.dataframe(df_other.head(10))
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
        
        if st.session_state.other_timetable is not None:
            if st.button("Clear Uploaded Timetable"):
                st.session_state.other_timetable = None
                st.rerun()
    
    # TAB 6: GENERATE & VIEW
    with tab6:
        st.header("Generate & View Timetable")
        
        # Color options
        color_options = {
            'Red': '#ff6b6b',
            'Blue': '#4ecdc4',
            'Green': '#95e1d3',
            'Yellow': '#fce38a',
            'Orange': '#f38181',
            'Purple': '#aa96da',
            'Pink': '#fcbad3',
            'Gray': '#d3d3d3',
            'White': '#ffffff',
            'Black': '#000000'
        }
        
        selected_class = st.selectbox("Select Class", st.session_state.classes, key="view_class")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Generate Timetable", type="primary"):
                try:
                    with st.spinner("Generating timetable..."):
                        # Validate inputs first
                        if not st.session_state.time_slots:
                            st.error("Please define time slots in the 'Time Slots' tab first.")
                        elif not st.session_state.classes:
                            st.error("Please define classes in the 'Setup' tab first.")
                        else:
                            df, all_slots = generate_timetable_grid(
                                selected_class,
                                st.session_state.days,
                                st.session_state.time_slots
                            )
                            
                            # Apply fixed events
                            if st.session_state.fixed_events:
                                apply_fixed_events(df, all_slots, st.session_state.fixed_events)
                            
                            # Apply fixed assignments
                            if st.session_state.fixed_assignments:
                                apply_fixed_assignments(df, all_slots, st.session_state.fixed_assignments, selected_class)
                            
                            # Auto-generate subjects
                            if st.session_state.subjects:
                                auto_generate_subjects(df, all_slots, selected_class, st.session_state.subjects)
                            
                            # Store in session state (limit size to prevent memory issues)
                            st.session_state.timetable_data[selected_class] = (df, all_slots)
                            st.session_state.generation_status[selected_class] = "Generated"
                            
                            # Clean up old data if too many classes
                            if len(st.session_state.timetable_data) > 10:
                                oldest_class = list(st.session_state.timetable_data.keys())[0]
                                del st.session_state.timetable_data[oldest_class]
                            
                            st.success(f"Timetable generated for {selected_class}!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error generating timetable: {str(e)}")
                    if st.checkbox("Show detailed error", key="show_error"):
                        st.code(traceback.format_exc())
        
        with col2:
            if st.button("🔍 Check Clashes"):
                if selected_class in st.session_state.timetable_data:
                    clashes = check_teacher_clashes(st.session_state.timetable_data, selected_class)
                    if clashes:
                        st.error("**Clashes Found:**")
                        for clash in clashes:
                            st.error(f"⚠️ {clash}")
                    else:
                        st.success("✅ No clashes detected!")
        
        # Display timetable
        if selected_class in st.session_state.timetable_data:
            df, all_slots = st.session_state.timetable_data[selected_class]
            
            st.markdown(f'<div class="school-name">{st.session_state.school_name} - {selected_class}</div>', unsafe_allow_html=True)
            
            # Color customization
            st.subheader("Color Customization")
            st.caption("Select colors for timetable cells")
            
            # Get unique values in timetable
            unique_values = set()
            for day in st.session_state.days:
                for idx in range(len(df)):
                    value = str(df.loc[df.index[idx], day])
                    if value:
                        unique_values.add(value.split('(')[0].strip())
            
            if unique_values:
                color_mapping = {}
                for value in sorted(unique_values):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{value}**")
                    with col2:
                        current_color = st.session_state.timetable_colors.get(selected_class, {}).get(value, '#ffffff')
                        color_name = [k for k, v in color_options.items() if v == current_color]
                        selected_color_name = st.selectbox(
                            "Color",
                            list(color_options.keys()),
                            index=list(color_options.keys()).index(color_name[0]) if color_name else 0,
                            key=f"color_{selected_class}_{value}"
                        )
                        color_mapping[value] = color_options[selected_color_name]
                
                if selected_class not in st.session_state.timetable_colors:
                    st.session_state.timetable_colors[selected_class] = {}
                st.session_state.timetable_colors[selected_class].update(color_mapping)
            
            # Display styled timetable
            st.subheader("Timetable View")
            
            # Create HTML table with colors
            html_table = f"""
            <div class="timetable-container">
                <table class="timetable-table">
                    <thead>
                        <tr>
                            <th class="period-header">Time Slots</th>
            """
            for day in st.session_state.days:
                html_table += f'<th class="period-header">{day}</th>'
            html_table += "</tr></thead><tbody>"
            
            for idx, slot in enumerate(all_slots):
                html_table += f"<tr><td><strong>{df.index[idx]}</strong></td>"
                for day in st.session_state.days:
                    cell_value = str(df.loc[df.index[idx], day])
                    # Get color
                    cell_key = cell_value.split('(')[0].strip() if cell_value else ''
                    bg_color = st.session_state.timetable_colors.get(selected_class, {}).get(cell_key, '#ffffff')
                    text_color = '#000000' if bg_color != '#000000' else '#ffffff'
                    
                    html_table += f'<td style="background-color: {bg_color}; color: {text_color};">{cell_value}</td>'
                html_table += "</tr>"
            
            html_table += "</tbody></table></div>"
            st.markdown(html_table, unsafe_allow_html=True)
            
            # Export options
            st.markdown("---")
            st.subheader("Export Options")
            
            col1, col2 = st.columns(2)
            with col1:
                csv_data = df.to_csv(index=True)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=f"{st.session_state.school_name.replace(' ', '_')}_{selected_class}_timetable.csv",
                    mime="text/csv"
                )
            
            with col2:
                try:
                    excel_data = export_to_excel({selected_class: (df, all_slots)})
                    st.download_button(
                        label="📥 Download Excel",
                        data=excel_data,
                        file_name=f"{st.session_state.school_name.replace(' ', '_')}_{selected_class}_timetable.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.warning(f"Excel export requires openpyxl. Install with: pip install openpyxl")
        
        else:
            st.info("Generate a timetable first using the button above.")
    
    # Sidebar
    with st.sidebar:
        st.header("ℹ️ About")
        st.write("""
        Ghana Timetable Generator for JHS schools.
        
        **Features:**
        - Multiple classes support
        - Customizable time slots per day
        - Fixed events & assignments
        - Automatic subject generation
        - Teacher clash detection
        - Color customization
        - Export to CSV/Excel
        """)
        
        st.markdown("---")
        if st.button("🔄 Reset All Data"):
            try:
                # Clear large data structures first
                if 'timetable_data' in st.session_state:
                    del st.session_state.timetable_data
                if 'other_timetable' in st.session_state:
                    del st.session_state.other_timetable
                # Reset to defaults
                for key in list(st.session_state.keys()):
                    if key != 'app_ready':
                        del st.session_state[key]
                init_session_state()
                st.success("Data reset successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error resetting data: {str(e)}")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.error("Please refresh the page. If the problem persists, check the console for details.")
    st.code(traceback.format_exc())
