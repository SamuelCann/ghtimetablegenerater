# Ghana School Timetable Generator

A web application built with Streamlit for creating customizable school timetables for Ghanaian schools.

## Features

- Customizable days and periods
- Subject management with weekly hours tracking
- Custom text entries (P.E, Assembly, etc.)
- Fixed/non-negotiable time slots
- Clash detection
- Export to CSV/JSON
- Printable format

## Installation

1. Clone this repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate the virtual environment:
   - Windows: `.venv\Scripts\Activate.ps1`
   - Mac/Linux: `source .venv/bin/activate`
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the app:
   ```bash
   streamlit run app.py
   ```

## Usage

1. Configure your school settings (name, days, periods, subjects)
2. Generate a blank timetable
3. Fill in the timetable manually or set fixed items
4. Check for clashes
5. Export when ready

## Author

By Samuel Nhyira
