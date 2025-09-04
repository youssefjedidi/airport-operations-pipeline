# SECTION 1: IMPORTS & SETUP

import os
import requests
import csv
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

from config import AIRPORT_IATA, AIRPORT_NAME, TURNAROUND_THRESHOLD_MINUTES, LOG_FILE_PATH

load_dotenv()
# AVIATION_STACK_API_KEY = os.getenv('AVIATIONSTACK_API_KEY')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
STATE_FILE = 'flight_tracker.json'
 
# API_BASE_URL = 'http://api.aviationstack.com/v1/flights'

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
def load_state():
    """Loads the flight tracking data from a JSON file."""
    try:
        with open(STATE_FILE, 'r') as f:
            state_data = json.load(f)
            # Convert string timestamps back to datetime objects
            for callsign, data in state_data.items():
                data['first_seen_utc'] = datetime.fromisoformat(data['first_seen_utc'])
            return state_data
    except FileNotFoundError:
        return {} # No state file found, start fresh

def save_state(state_data):
    """Saves the flight tracking data to a JSON file."""
    # Convert datetime objects to strings for JSON serialization
    serializable_data = {}
    for callsign, data in state_data.items():
        serializable_data[callsign] = {
            'first_seen_utc': data['first_seen_utc'].isoformat()
        }
    with open(STATE_FILE, 'w') as f:
        json.dump(serializable_data, f, indent=4)

def process_and_log_data(state_vectors):
    """
    Processes OpenSky state vector data to identify aircraft on the ground,
    calculates true time on ground using a persistent state file,
    and logs relevant information to a CSV file.
    """
    if not state_vectors:
        print("No state vector data to process.")
        return []

    print("Processing OpenSky state vector data...")

    # Load the memory of planes we are already tracking
    state_tracker = load_state()
    
    current_time_utc = datetime.now(timezone.utc)
    all_grounded_flights_log = []
    flagged_for_alert = []
    
    # Keep track of planes seen in this specific API call
    current_live_callsigns = set()

    for state in state_vectors:
        # State vector indices based on OpenSky API documentation
        # 0: icao24, 1: callsign, 2: origin_country, 3: time_position,
        # 4: last_contact, 5: longitude, 6: latitude, 7: baro_altitude,
        # 8: on_ground, 9: velocity, 10: true_track, 11: vertical_rate,
        # 12: sensors, 13: geo_altitude, 14: squawk, 15: spi, 16: position_source

        # We only care about aircraft that are on the ground.
        if state[8] is True:  # state[8] is 'on_ground'
            callsign = state[1].strip() if state[1] else 'N/A'
            if callsign == 'N/A':
                continue # Skip entries without a proper callsign

            current_live_callsigns.add(callsign)

            # --- STATEFUL LOGIC START ---
            if callsign not in state_tracker:
                # NEW PLANE DETECTED: Record its landing time.
                state_tracker[callsign] = {
                    'first_seen_utc': current_time_utc
                }
                true_minutes_on_ground = 0
            else:
                # EXISTING PLANE: Calculate total time since first detection.
                first_seen_time = state_tracker[callsign]['first_seen_utc']
                duration = current_time_utc - first_seen_time
                true_minutes_on_ground = int(duration.total_seconds() / 60)
            # --- STATEFUL LOGIC END ---

            # Log entry creation
            flight_log_entry = {
                'log_timestamp_utc': current_time_utc.isoformat(),
                'flight_iata': callsign,
                'airline': "Unknown",
                'origin_country': state[2] if state[2] else 'N/A',
                'last_contact_time_utc': datetime.fromtimestamp(state[4], tz=timezone.utc).isoformat(),
                'minutes_on_ground': true_minutes_on_ground # Use the correct calculation here
            }
            all_grounded_flights_log.append(flight_log_entry)

            # Check threshold for alerts
            if true_minutes_on_ground > TURNAROUND_THRESHOLD_MINUTES:
                # Optional: prevent sending duplicate alerts every run
                if not state_tracker[callsign].get('alert_sent', False):
                    flagged_for_alert.append(flight_log_entry)
                    state_tracker[callsign]['alert_sent'] = True # Mark alert as sent

    # --- CLEANUP LOGIC ---
    # Remove planes from tracker that have departed (are no longer seen on ground)
    departed_planes = set(state_tracker.keys()) - current_live_callsigns
    for callsign in departed_planes:
        print(f"Removing departed flight {callsign} from tracker.")
        del state_tracker[callsign]

    # Save updated state back to file for next run
    save_state(state_tracker)

    # Log all currently grounded flights to CSV
    _save_logs_to_csv(all_grounded_flights_log)

    print(f"Processed {len(state_vectors)} aircraft. Found {len(all_grounded_flights_log)} on the ground. {len(flagged_for_alert)} flagged.")
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

    with open(LOG_FILE_PATH, mode='a', newline='', encoding='utf-8') as csvfile:
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
    