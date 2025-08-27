# SECTION 1: IMPORTS & SETUP

import os
import requests
import csv
from datetime import datetime, timezone
from dotenv import load_dotenv

from config import AIRPORT_IATA, AIRPORT_NAME, TURNAROUND_THRESHOLD_MINUTES, LOG_FILE_PATH

load_dotenv()
AVIATION_STACK_API_KEY = os.getenv('AVIATIONSTACK_API_KEY')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

API_BASE_URL = 'http://api.aviationstack.com/v1/flights'
# API_BASE_URL = 'https://opensky-network.org/api/states/all  '

# SECTION 2: FETCHING DATA 

def fetch_flight_data():
    """
    Fetches flight data from the aviationstack API
    """

    params = {
        'access_key': AVIATION_STACK_API_KEY,
        'flight_iata': AIRPORT_IATA,
        'flight_status': 'landed',  # 'landed' could be used if we want only completed flights
        # 'limit': 100
        }
    
    print("Fetching live flight data...")

    try:
        response = requests.get(API_BASE_URL, params=params)
        response.raise_for_status()

        data = response.json().get('data', [])
        print(f"Successfuly Fetched data for {len(data)} landed flights records.")
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error: could not fetch data from aviationstack API. {e}")
        return []

def fetch_opensky_data():
    """   
    Fetches real-time flight state data for aircraft near Montreal (YUL)
    from the OpenSky Network API.
    """

    params = {
        'lamin': 45.3,  # Minimum latitude for Montreal area
        'lamax': 45.7,  # Maximum latitude for Montreal area
        'lomin': -74.1, # Minimum longitude for Montreal area
        'lomax': -73.5  # Maximum longitude for Montreal area
    # 'lamin': 51.3,
    # 'lomin': -0.6,
    # 'lamax': 51.7,
    # 'lomax': -0.3,
    }

    OPENSKY_API_URL = 'https://opensky-network.org/api/states/all'
    print("Fetching live flight data from OpenSky Network...")

    try:
        response = requests.get(OPENSKY_API_URL, params=params, timeout=15)
        response.raise_for_status()

        state_vectors = response.json().get('states', [])

        if state_vectors is None:
            print("No state vectors found in the OpenSky response.")
            return []
        
        print(f"Successfully fetched state vectors for {len(state_vectors)} aircraft in the YUL area from OpenSky.")
        return state_vectors
    
    except requests.exceptions.RequestException as e:
        print(f"Error: could not fetch data from OpenSky Network API. {e}")
        return []


# SECTION 3: PROCESSING DATA & LOGGING

# def process_and_log_data(flights):
#     """
#     Processes flight data to calculate turnaround times and logs to CSV.
#     takes the raw flight data, calculates turnaround times , logs everything,
#     and identifies flights that need an alert based on the threshold.
#     """

#     if not flights: # A "guard clause": if we got no flights, just stop right away.
#         print("No flight data to process.")
#         return []
    
#     print("Processing flight data...")

#     all_landed_flights_log = []
#     flagged_for_alert = []

#     for flight in flights:
#         if not flight.get('arrival') or not flight.get('arrival').get('actual'):
#             continue 

#         # convert text timestamp from API into datetime object for TimeKeeper library calculations
#         arrival_time_str = flight['arrival']['actual']
#         arrival_time = datetime.fromisoformat(arrival_time_str)
    
#         time_on_ground = datetime.now(timezone.utc) - arrival_time
#         minutes_on_ground = int(time_on_ground.total_seconds() / 60)

#         flight_log_entry = {
#             'log_timestamp_utc': datetime.now(timezone.utc).isoformat(),
#             'flight_iata': flight.get('flight', {}).get('iata', 'N/A'),
#             # 'flight_iata': flight['flight']['iata'],
#             'airline': flight.get('airline', {}).get('name', 'N/A'),
#             # 'flight_number': flight.get('flight', {}).get('number', 'N/A'),
#             'arrival_from' : flight.get('departure', {}).get('iata', 'N/A'),
#             # 'arrival_time_utc': arrival_time_str,
#             'arrival_time_utc': arrival_time.isoformat(),
#             'minutes_on_ground': minutes_on_ground,
#             # 'airport': AIRPORT_IATA
#         }
#         all_landed_flights_log.append(flight_log_entry)

#         if minutes_on_ground > TURNAROUND_THRESHOLD_MINUTES:
#             flagged_for_alert.append(flight_log_entry)
    
#     # Log all landed flights to CSV
#     _save_logs_to_csv(all_landed_flights_log)

#     print(f"Processed {len(all_landed_flights_log)} landed flights. {len(flagged_for_alert)} flagged for alert.")
#     return flagged_for_alert

def process_and_log_data(state_vectors):
    """
    Processes OpenSky state vector data to identify aircraft on the ground
    and logs relevant information to a CSV file.
    Identifies aircraft that have been on the ground too long based on the threshold.
    """

    if not state_vectors: # A "guard clause": if we got no state vectors, just stop right away.
        print("No state vector data to process.")
        return []
    
    print("Processing OpenSky state vector data...")

    all_grounded_flights_log = []
    flagged_for_alert = []

    # current_time_utc = datetime.now(timezone.utc)

    for state in state_vectors:
        # State vector indices based on OpenSky API documentation
        # 0: icao24, 1: callsign, 2: origin_country, 3: time_position,
        # 4: last_contact, 5: longitude, 6: latitude, 7: baro_altitude,
        # 8: on_ground, 9: velocity, 10: true_track, 11: vertical_rate,
        # 12: sensors, 13: geo_altitude, 14: squawk, 15: spi, 16: position_source

        # We only care about aircraft that are on the ground.
        if state[8] is True:
            callsign = state[1].strip() if state[1] else 'N/A'

            # last_contact is a Unix timestamp (seconds since 1970). We must convert it.
            last_contact_time = datetime.fromtimestamp(state[4], tz=timezone.utc)

            time_on_ground = datetime.now(timezone.utc) - last_contact_time
            minutes_on_ground = int(time_on_ground.total_seconds() / 60)

            flight_log_entry = {
                'log_timestamp_utc': datetime.now(timezone.utc).isoformat(),
                'flight_iata': callsign,
                'airline': "Unknown", # OpenSky doesn't provide airline name directly
                # 'arrival_from': "Unknown", # Or arrival airport
                'origin_country': state[2] if state[2] else 'N/A',
                'last_contact_time_utc': last_contact_time.isoformat(),
                'minutes_on_ground': minutes_on_ground,
                # 'airport': AIRPORT_IATA
            }
            all_grounded_flights_log.append(flight_log_entry)

            if minutes_on_ground > TURNAROUND_THRESHOLD_MINUTES:
                flagged_for_alert.append(flight_log_entry)
            
    # Log all grounded flights to CSV
    _save_logs_to_csv(all_grounded_flights_log)

    print(f"Processed {len(state_vectors)} aircraft. Found {len(all_grounded_flights_log)} on the ground. {len(flagged_for_alert)} flagged.")
    # print(f"Processed {len(all_grounded_flights_log)} grounded aircraft. {len(flagged_for_alert)} flagged for alert.")
    return flagged_for_alert

def _save_logs_to_csv(log_entries):
    """
    Internal helper function to append log entries to our CSV file.
    Saves log entries to a CSV file.
    Creates the file with headers if it doesn't exist.
    Appends to it if it does.
    """

    # Guard clause:
    if not log_entries:
        # If the list is empty, there is nothing to save. Stop right here.
        return 

    file_exists = os.path.isfile(LOG_FILE_PATH)


    # os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

    with open(LOG_FILE_PATH, mode='a', newline='', encoding='utf-8') as csvfile:
        # fieldnames = ['log_timestamp_utc', 'flight_iata', 'airline', 'arrival_from', 'arrival_time_utc', 'minutes_on_ground']
        fieldnames =log_entries[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # We only write the header row if the file is brand new.
        if not file_exists:
            writer.writeheader()
        
        # for entry in log_entries:
        # The Scribe writes all our processed log entries to the file.
        writer.writerows(log_entries)
    
    print(f"Successfully logged {len(log_entries)} entries to {LOG_FILE_PATH}")

# SECTION 4: ALERTING

def send_slack_alert(flagged_flights):
    """
    Formats and sends a summary of flagged flights to a Slack channel.
    Sends an alert to Slack for flights that have been on the ground too long.
    """
    if not flagged_flights:
        print("No flights flagged for alert. No Slack message sent.")
        return
    

    message_lines = [
        f":warning: *Alert: {len(flagged_flights)} flights at {AIRPORT_NAME} ({AIRPORT_IATA}) have been on the ground for over {TURNAROUND_THRESHOLD_MINUTES} minutes!* :warning:",
        "",
        "Here are the details:"
    ]

    for flight in flagged_flights:
        line = (            
            f"\n*- Flight {flight['flight_iata']}* ({flight['airline']})\n"
            f"  - Arrived from: {flight['origin_country']}\n"
            f"  - On ground for: *{flight['minutes_on_ground']} minutes*\n"
            # f"  - Arrival time (UTC): {flight['arrival_time_utc']}\n"
        )
        message_lines.append(line)
    
    message = "\n".join(message_lines)

    payload = {
        "text": message
    }

    try:
        print("Sending Slack alert...")
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Slack alert sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error: could not send Slack alert. {e}")
    
# SECTION 5: MAIN EXECUTION FLOW
if __name__ == "__main__":
    print(f"--- Starting Airport Operations Monitor at {datetime.now()} ---")
    
    # 1. Fetch the data using our NEW OpenSky function
    raw_flights = fetch_opensky_data()
    
    # 2. Process, log, and identify flights to alert on
    flights_to_alert = process_and_log_data(raw_flights)
    
    # 3. Send an alert if necessary
    send_slack_alert(flights_to_alert)
    
    print(f"--- Monitor run finished at {datetime.now()} ---")
    
    # print(f"--- Starting Airport Operations Monitor at {datetime.now()} ---")

    # raw_flight_data = fetch_flight_data()

    # flights_to_alert = process_and_log_data(raw_flight_data)

    # send_slack_alert(flights_to_alert)

    # print(f"--- Monitor run complete at {datetime.now()} ---\n")

    # # --- TEMPORARY TEST CODE ---
    # # We are creating fake data to simulate a long turnaround flight
    # fake_flights = [
    #     {
    #         'flight': {'iata': 'AC427'},
    #         'airline': {'name': 'Air Canada'},
    #         'departure': {'iata': 'YYZ'},
    #         'arrival': {
    #             # Make the arrival time 2 hours ago to guarantee a flagged alert
    #             'actual': datetime.now(timezone.utc).replace(hour=datetime.now(timezone.utc).hour - 2).isoformat()
    #         }
    #     }
    # ]
    
    # # We are skipping the real API call and using our fake data instead
    # raw_flights = fake_flights
    # print("Using fake data for testing purposes.")
    # # --- END OF TEMPORARY TEST CODE ---

    # # The rest of the script runs as normal, using our fake data
    # flights_to_alert = process_and_log_data(raw_flights)
    # send_slack_alert(flights_to_alert)
    
    # print(f"--- Monitor run finished at {datetime.now()} ---")