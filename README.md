# School Lunch Planner

A simple desktop application that creates a weekday school lunch schedule from
a CSV menu. It runs locally on your computer and does not require a web server
or an internet connection.

## Features

- Plans one lunch for every school day, Monday through Friday
- Uses only dishes available on each weekday
- Prevents the same protein from appearing on consecutive school days
- Limits each protein to two appearances per week
- Schedules sushi once every two complete school weeks
- Schedules three rice dishes in a sushi week and four in a non-sushi week
- Lets you regenerate or remove an individual day's lunch
- Can optionally import no-school dates from Google Calendar

## What you need

- Python 3.10 or newer
- Tkinter, which is included with the standard Python installer on macOS and
  Windows
- A menu saved as a `.csv` file

No additional Python packages are required.

## Download the project

1. On the GitHub repository page, click **Code**.
2. Click **Download ZIP**.
3. Open the downloaded ZIP file.
4. Move the extracted folder somewhere you want to keep it, such as your
   Desktop or Documents folder.

Keep `lunch_planner.py` and `planner_core.py` together in the same folder.

## Run on macOS

1. Install Python from [python.org](https://www.python.org/downloads/) if it is
   not already installed.
2. Open **Terminal**.
3. Type `python3 `, including the space after it.
4. Drag `lunch_planner.py` from Finder into the Terminal window.
5. Press **Return**.

The final command will look similar to this:

```bash
python3 /Users/your-name/Desktop/school-lunch-menu-planner/lunch_planner.py
```

## Run on Windows

1. Install Python from [python.org](https://www.python.org/downloads/). During
   installation, select **Add Python to PATH**.
2. Open the project folder in File Explorer.
3. Right-click an empty area in the folder and choose **Open in Terminal**.
4. Run:

```powershell
python lunch_planner.py
```

If `python` is not recognized, try:

```powershell
py lunch_planner.py
```

## Run on Linux

Open a terminal in the project folder and run:

```bash
python3 lunch_planner.py
```

Some Linux distributions install Tkinter separately. For example, on Ubuntu or
Debian:

```bash
sudo apt install python3-tk
```

## Prepare the menu CSV

The first row must contain these seven columns in this exact order:

```text
dish name,restaurant name,day availability,regular price,large price (if applicable),protein type,base type
```

Example:

```csv
dish name,restaurant name,day availability,regular price,large price (if applicable),protein type,base type
Chicken Teriyaki,Example Restaurant,"Monday, Wednesday, Friday",10.00,12.00,C,Rice
Pork Dumplings,Example Restaurant,All,9.00,,P,Handheld
Salmon Roll,Example Restaurant,Thursday,11.00,,S,Sushi
```

CSV values:

- **Day availability:** Use `All` for Monday through Friday, or list specific
  days separated by commas, such as `Monday, Wednesday, Friday`.
- **Protein type:** Use `C` for chicken, `P` for pork, `B` for beef, and `S` for
  shrimp. Combined codes such as `CP` are supported and count toward both
  proteins. An unrecognized value is treated as “other.”
- **Base type:** Use `Rice` and `Sushi` exactly when those rules should apply.
  Other values, such as `Soup Noodle` or `Handheld`, are grouped as other
  dishes.
- **Large price:** This field may be left empty. All other fields are required.

If a cell contains commas, spreadsheet software will normally add quotation
marks automatically when exporting the file as CSV.

## Create a lunch schedule

1. Start the application.
2. Click **Choose CSV** and select your menu file.
3. Select a month.
4. Click **Generate menu**.
5. Use **Regenerate** to replace one day's meal with another valid dish.
6. Use **Remove** to mark a date as **No school**.

Generating a new menu or changing the month clears dates that were manually
removed.

If the app cannot create a complete schedule, it will explain the problem. Add
more varied dishes or make more dishes available throughout the week, then try
again. The planner does not silently ignore its scheduling rules.

## Optional Google Calendar setup

The app works fully offline. Google Calendar is only needed if you want it to
automatically mark all-day calendar events as no-school dates.

Before starting the app, set these environment variables:

```text
GOOGLE_CALENDAR_API_KEY
GOOGLE_SCHOOL_CALENDAR_ID
```

The calendar must be readable with the provided Google Calendar API key. Only
all-day events are imported; timed events are ignored. Never place an API key
inside the CSV or commit it to GitHub.

## Troubleshooting

### The app says no valid menu can be created

Make sure the CSV has enough choices to satisfy all scheduling rules. In
particular, each active weekday needs at least one available dish, and the menu
needs enough rice, sushi, and protein variety.

### Python reports that Tkinter is missing

Reinstall Python using the official installer from python.org. On Linux,
install your distribution's Tkinter package, commonly named `python3-tk`.

### The CSV is rejected

Check that it has exactly seven columns in the required order and that required
cells are not blank. Export the file as **CSV UTF-8** when that option is
available.

## Run the tests

This step is optional and is mainly useful for contributors:

```bash
python3 -m unittest discover -s tests -v
```

## Privacy

Menu data stays on your computer. The app only connects to the internet when
Google Calendar credentials are configured, and then only to read calendar
events.
