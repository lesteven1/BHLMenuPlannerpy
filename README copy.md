# School lunch planner (Python)

Run `python3 lunch_planner.py` from this folder. The app uses Python 3.10+ and
Tkinter; no pip packages or web server are needed. In the window, choose a CSV,
select a month, and click **Generate menu**. Use **Regenerate** or **Remove** on
individual dates. Removed dates stay marked **No school** until you generate a
new menu or change months.

The CSV must contain these headers in this order (case-insensitive):

```text
dish name,restaurant name,day availability,regular price,large price (if applicable),protein type,base type
```

`All` means Monday–Friday. Comma-separated days such as `Thurs, Fri` are also
accepted. Mixed protein codes count toward every recognized protein they
contain. The app never silently relaxes scheduling rules; it reports when no
valid complete plan can be found.

Google Calendar is optional. To import all-day events as school closures, set
`GOOGLE_CALENDAR_API_KEY` and `GOOGLE_SCHOOL_CALENDAR_ID` in your environment
before starting the app. It only reads calendar events. Without both values,
the app works entirely offline and dates can be removed manually. Never put a
private API key in a CSV or share it with the app files.

Run the non-GUI tests with `python3 -m unittest discover -s tests -v`.
