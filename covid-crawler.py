import threading
from tksheet import Sheet
import requests
from geopy import distance
from geopy.geocoders import Nominatim
import pandas as pd
import webbrowser as wb
import tkinter as tk
import platform

geolocator = Nominatim(user_agent="covid-crawler")
searching = True
thread_event = threading.Event()

us_state_abbrev = {
    'Alabama': 'AL',
    'Alaska': 'AK',
    'American Samoa': 'AS',
    'Arizona': 'AZ',
    'Arkansas': 'AR',
    'California': 'CA',
    'Colorado': 'CO',
    'Connecticut': 'CT',
    'Delaware': 'DE',
    'District of Columbia': 'DC',
    'Florida': 'FL',
    'Georgia': 'GA',
    'Guam': 'GU',
    'Hawaii': 'HI',
    'Idaho': 'ID',
    'Illinois': 'IL',
    'Indiana': 'IN',
    'Iowa': 'IA',
    'Kansas': 'KS',
    'Kentucky': 'KY',
    'Louisiana': 'LA',
    'Maine': 'ME',
    'Maryland': 'MD',
    'Massachusetts': 'MA',
    'Michigan': 'MI',
    'Minnesota': 'MN',
    'Mississippi': 'MS',
    'Missouri': 'MO',
    'Montana': 'MT',
    'Nebraska': 'NE',
    'Nevada': 'NV',
    'New Hampshire': 'NH',
    'New Jersey': 'NJ',
    'New Mexico': 'NM',
    'New York': 'NY',
    'North Carolina': 'NC',
    'North Dakota': 'ND',
    'Northern Mariana Islands': 'MP',
    'Ohio': 'OH',
    'Oklahoma': 'OK',
    'Oregon': 'OR',
    'Pennsylvania': 'PA',
    'Puerto Rico': 'PR',
    'Rhode Island': 'RI',
    'South Carolina': 'SC',
    'South Dakota': 'SD',
    'Tennessee': 'TN',
    'Texas': 'TX',
    'Utah': 'UT',
    'Vermont': 'VT',
    'Virgin Islands': 'VI',
    'Virginia': 'VA',
    'Washington': 'WA',
    'West Virginia': 'WV',
    'Wisconsin': 'WI',
    'Wyoming': 'WY'
}


def cell_selected(event=None):
    r, c = sheet.get_currently_selected()

    url = sheet.get_cell_data(r, 2)

    if platform.system() == 'Windows':
        wb.get('windows-default').open(url)
    else:
        wb.get('macosx').open(url)


def start_search():
    th = threading.Thread(target=search)
    th.daemon = True
    th.start()


def stop_search():
    global searching
    global thread_event
    searching = False
    search_button.configure(text='Stopping...')
    search_button["state"] = "disabled"
    thread_event.set()


def search():
    global search_button
    global searching
    global thread_event
    search_button.configure(text="Stop Searching", command=stop_search)
    address_entry['state'] = 'disabled'

    try:
        geocode = geolocator.geocode(address_entry.get(), addressdetails=True)
        print(geocode.address)
        state = geocode.raw['address']['state']

        current_location = (geocode.latitude, geocode.longitude)

        searching = True
        while searching:
            resp = requests.get(f'https://www.vaccinespotter.org/api/v0/states/{us_state_abbrev[state]}.json')
            resp_json = resp.json()
            locations_with_vaccines = []
            for location in resp_json['features']:
                if location['properties']['appointments_available']:
                    location_coordinates = (location['geometry']['coordinates'][1], location['geometry']['coordinates'][0])
                    location['distance'] = round(distance.distance(current_location, location_coordinates).miles, 2)
                    locations_with_vaccines.append(location)

            locations_with_vaccines = sorted(locations_with_vaccines, key=lambda l: l['distance'])
            now = pd.to_datetime("now", utc=True)
            ignored_locations = []
            data = []
            for location in locations_with_vaccines:
                location_name = location['properties']['name']
                location_address = f"{location['properties']['name']}, {location['properties']['address']}, {location['properties']['city']}"
                scan_date = pd.to_datetime(location['properties']['appointments_last_fetched'], utc=True)
                staleness = round(pd.Timedelta(now - scan_date).seconds / 60.0, 2)

                if location['distance'] < float(distance_entry.get()):
                    print(f"Found vaccine appointment: {location_name}, {location_address}, vaccine types: {list(location['properties']['appointment_vaccine_types'].keys())}, distance: {location['distance']} miles, staleness: {staleness} mins")

                    if((pfizer_checkbox_var.get() == 1 and location['properties']['appointment_vaccine_types'].get('pfizer', False))
                    or ((moderna_checkbox_var.get() == 1 and location['properties']['appointment_vaccine_types'].get('moderna', False)))):
                        data.append([location_name, location_address, location['properties']['url'], list(location['properties']['appointment_vaccine_types'].keys()), location['distance'], staleness])
                else:
                    ignored_locations.append(location)

            sheet.set_sheet_data(data)
            print(f"Ignored {len(ignored_locations)} locations due to them being too far. (max distance was {distance_entry.get()} miles)")
            ignored_label.config(fg="black")
            if len(ignored_locations) > 0:
                print(f"Closest ignored location was {ignored_locations[0]['distance']} miles away")
                ignored_label_text.set(f"Ignored {len(ignored_locations)} locations due to them being too far.\nClosest ignored location was {ignored_locations[0]['distance']} miles away")
            else:
                ignored_label_text.set(f"Ignored {len(ignored_locations)} locations due to them being too far")

            master.update()
            print(f"Sleeping for {int(polling_interval_entry.get())} seconds" )
            thread_event = threading.Event()
            thread_event.wait(timeout=int(polling_interval_entry.get()))
    except:
        ignored_label_text.set("Invalid location (maybe try latitude/longitude?)")
        ignored_label.config(fg="red")
        master.update()
        print("Got an exception")

    print("Stopping search")
    search_button.configure(text='Start Search', command=start_search)
    address_entry['state'] = 'normal'
    search_button["state"] = "normal"


master = tk.Tk()
master.geometry("700x500")
master.title('Covid Crawler')
master.resizable(height=None, width=None)
tk.Label(master, text="Address or Coordinates").grid(row=0)
tk.Label(master, text="Max Travel Distance (miles)").grid(row=1)
tk.Label(master, text="Polling Interval (seconds)").grid(row=2)

address_entry = tk.Entry(master)
address_entry.insert(0, "")
distance_entry = tk.Entry(master)
distance_entry.insert(0, "150")
polling_interval_entry = tk.Entry(master)
polling_interval_entry.insert(0, "10")

type_frame = tk.Frame(master)

moderna_checkbox_var = tk.IntVar(value=1)
pfizer_checkbox_var = tk.IntVar(value=1)

moderna_checkbox = tk.Checkbutton(master, text="Moderna", variable=moderna_checkbox_var)
pfizer_checkbox = tk.Checkbutton(master, text="Pfizer", variable=pfizer_checkbox_var)

address_entry.grid(row=0, column=1, sticky='nswe')
distance_entry.grid(row=1, column=1, sticky='nswe')
polling_interval_entry.grid(row=2, column=1, sticky='nswe')

moderna_checkbox.grid(row=3, column=0)
pfizer_checkbox.grid(row=3, column=1)

tk.Button(master,
          text='Quit',
          command=master.quit).grid(row=4,
                                    column=0,
                                    sticky='nswe',
                                    pady=4)

search_button = tk.Button(master, text='Start Search', command=start_search)
search_button.grid(row=4, column=1, sticky='nswe', pady=4)

tk.Label(master, text="Click any cell to open URL").grid(row=6, column=0)
ignored_label_text = tk.StringVar()
ignored_label = tk.Label(master, textvariable=ignored_label_text)
ignored_label.grid(row=6, column=1)
tk.Label(master, text="").grid(row=7, column=0)

sheet = Sheet(master,
              headers=['Name', 'Address', 'URL', 'Vaccine Types', 'Distance (miles)', 'Staleness (mins)'])
sheet.enable_bindings()
sheet.extra_bindings('cell_select', func=cell_selected)
sheet.grid(row=8, column=0, columnspan=2, sticky='nswe')
for x in range(2):
    tk.Grid.columnconfigure(master, x, weight=1)

for y in range(6):
    tk.Grid.rowconfigure(master, y, weight=1)


master.mainloop()


