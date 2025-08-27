import pandas as pd
import matplotlib.pyplot as plt
# import seaborn as sns
# import os
from config import AIRPORT_NAME, LOG_FILE_PATH, REPORT_IMAGE_PATH
from datetime import datetime

def load_and_clean_data():
    """
    Loads the turnaround log CSV, cleans it, and prepares it for analysis.
    - Converts timestamps to datetime objects.
    - Handles duplicates by keeping only the most recent entry for each flight.
    - Ensures turnaround times are numeric and handles missing values.
    """
    print(f"Loading data from {LOG_FILE_PATH}...")
    try:
        df = pd.read_csv(LOG_FILE_PATH)
    except FileNotFoundError:
        print(f"Error: The file {LOG_FILE_PATH} was not found. Please run monitor.py first to generate some data.")
        return pd.DataFrame()  # Return empty DataFrame if file not found
    
    df['flight_iata'] = df['flight_iata'].astype(str)
    #Data Cleaning and Pre-processing
    print("Cleaning data...")
    df['log_timestamp_utc'] = pd.to_datetime(df['log_timestamp_utc'], utc=True)

    #De-duplication: Keep only the most recent entry for each flight
    cleaned_df = df.sort_values('log_timestamp_utc').drop_duplicates(subset=['flight_iata'], keep='last')

    print(f"Data loaded and cleaned. Found {len(cleaned_df)} unique aircraft on the ground.")
    return cleaned_df

def analyze_results(df):
    """
    Perform analysis on the cleaned DataFrame to extract key metrics.
    """

    #Guard clause
    if df.empty:
        print("No data available for analysis.")
        return None
    
    print("Analyzing data...")

    unique_aircraft_count = df['flight_iata'].nunique() # Count of unique aircraft

    average_minutes_on_ground = df['minutes_on_ground'].mean() # Average turnaround time

    # .idxmax() finds the index (row number) of the maximum value in a column.
    # We then use .loc[] to retrieve the entire row for that aircraft.
    longest_turnaround_flight = df.loc[df['minutes_on_ground'].idxmax()]

    analysis_results = {
        'unique_aircraft_count': unique_aircraft_count,
        'average_minutes_on_ground': average_minutes_on_ground,
        'longest_turnaround_flight': longest_turnaround_flight 
    }

    print("Analysis complete.")
    return analysis_results

def create_visual_report(df, analysis_results):
    """
    Creates and saves a bar chart of the top 10 longest turnaround times.
    """
    #Guard clause
    if df.empty or analysis_results is None:
        print("No data available for visualization.")
        return

    print("Creating visual report...")

    top_10_flights = df.nlargest(10, 'minutes_on_ground').sort_values('minutes_on_ground', ascending=True)

    plt.figure(figsize=(12, 6))

    print(top_10_flights['flight_iata'])
    print(top_10_flights['minutes_on_ground'])
    plt.barh(top_10_flights['flight_iata'], top_10_flights['minutes_on_ground'], color='skyblue')

    plt.xlabel('Time on Ground (Minutes)')
    plt.ylabel('Flight Callsign')
    plt.title(f'Top 10 Longest Turnaround Times at {AIRPORT_NAME}')
    plt.grid(axis='x', alpha=0.75)

    for index, value in enumerate(top_10_flights['minutes_on_ground']):
        plt.text(value, index, f' {value:.1f} min', va='center')

    plt.tight_layout()
    plt.savefig(REPORT_IMAGE_PATH)
    plt.close()

    print(f"Visual report saved successfully to {REPORT_IMAGE_PATH}.")

if __name__ == "__main__":
    print(f"\n--- Starting Airport Operations Reporter at {datetime.now()} ---")

    cleaned_flight_data = load_and_clean_data()

    report_data = analyze_results(cleaned_flight_data)

    create_visual_report(cleaned_flight_data, report_data)

    if report_data:
        print("\n--- Analysis Summary ---")
        print(f"Total Unique Aircraft Logged: {report_data['unique_aircraft_count']}")
        print(f"Average Time on Ground: {report_data['average_minutes_on_ground']:.2f} minutes")
        print("\n--- Flight with Longest Turnaround ---")
        print(f"Callsign: {report_data['longest_turnaround_flight']['flight_iata']}")
        print(f"Time on Ground: {int(report_data['longest_turnaround_flight']['minutes_on_ground'])} minutes")
        print(f"Origin Country: {report_data['longest_turnaround_flight'].get('origin_country', 'N/A')}")
        print(f"Last Contact (UTC): {report_data['longest_turnaround_flight'].get('last_contact_time_utc', 'N/A')}")

    print(f"\n--- Reporter run finished. ---")