'''run_all_tests_w_time.py'''
'''run this in the terminal to get data that will later be processed by process_drone_coords.py to find offsets'''

import subprocess
import time
from datetime import datetime

GRID_DATA_FILE = "grid_data.py"
SUMMARY_FILE = "simulation_summary_50m.txt"

START_COORDS = [
    ("Grass near NRC", 27.714913, -97.328388),  # Grass near NRC
    ("Seahorse parking lot", 27.714109, -97.327416),  # Seahorse parking lot
    ("Grass outside Bell Library", 27.713359, -97.324324),  # Grass outside Bell Library
    ("Circular area outside HRI", 27.716402, -97.328298),  # Circular area outside HRI
    ("Central Receiving Parking Lot", 27.713548, -97.329299),  # Central Receiving Parking Lot
    ("Outside UC", 27.712363, -97.325987),  # Outside UC
    ("Outside Dolphin Building", 27.710660, -97.322446),  # Outside Dolphin Building
    ("Near Chapman Field", 27.709806, -97.323921),  # Near Chapman Field
]

END_COORDS = [
    #("Outside my window at Momentum Village", 27.702977, -97.336979), # Outside my window at Momentum Village
    ("Angelfish Parking Lot", 27.714521, -97.325567), # Angelfish Parking Lot
    ("Jellyfish Parking Lot", 27.712431, -97.327000), # Jellyfish Parking Lot
    ("Turtle Cove Parking Lot", 27.710927, -97.325776), # Turtle Cove Parking Lot
    ("Curlew Parking Lot", 27.712358, -97.323117), # Curlew Parking Lot
    ("Seabreeze Parking Lot", 27.713148, -97.322307), # Seabreeze Parking Lot
    ("Tarpon Parking Lot", 27.712794, -97.321336), # Tarpon Parking Lot
    ("Sanddollar Parking lot", 27.713890, -97.321072), # Sanddollar Parking lot
    ("Hammerhead Parking Lot", 27.713033, -97.319548), #Hammerhead Parking Lot
]

def update_grid_data(start_lat, start_long, end_lat, end_long):
    with open(GRID_DATA_FILE, "r") as f:
        lines = f.readlines()

    new_lines = []

    for line in lines:
        clean=line.strip()
        if clean.strip().startswith("start_lat"):
            new_lines.append(f"start_lat = {start_lat}\n")
        elif clean.strip().startswith("start_long"):
            new_lines.append(f"start_long = {start_long}\n")
        elif clean.strip().startswith("end_lat"):
            new_lines.append(f"end_lat = {end_lat}\n")
        elif clean.strip().startswith("end_long"):
            new_lines.append(f"end_long = {end_long}\n")
        else:
            new_lines.append(line)

    with open(GRID_DATA_FILE, "w") as f:
        f.writelines(new_lines)

def stop_simulation():
    print("Stopping sim...")
    try:
        subprocess.run(["./stop_sim.sh"])
    except Exception as e:
        print(f"ERROR MIJA! What it is: {e}")

def run_simulation():
    try:
        print("Launching master_launch.sh...")
        subprocess.Popen(["./master_launch.sh"])

        print("Waiting 60s for stack initialization...")
        time.sleep(60)

        print("Monitoring fly.py...")
        max_timeout_seconds = 300
        elapsed = 0

        while elapsed < max_timeout_seconds:
            result = subprocess.run(["pgrep", "-f", "fly.py"], capture_output=True, text=True)
            if not result.stdout.strip():
                print(f"fly.py finished running or stopped because there was error")
                break
            time.sleep(5)
            elapsed += 5

        if elapsed >= max_timeout_seconds:
            print("Flight timed out, killing process..")

        time.sleep(5)

    finally:
        stop_simulation()
        time.sleep(5)


def main():
    total_tests = len(START_COORDS) * len(END_COORDS)
    run_counter = 1
    run_durations = []

    start_time = datetime.now()
    time_format = "%Y-%m-%d %H:%M:%S"

    try:
        for start_name, s_lat, s_lon in START_COORDS:
            for end_name, e_lat, e_lon in END_COORDS:
                print(f"\n--------------------------------------------------------")
                print(f"Testing flight: {start_name} ---> {end_name}")
                print(f" RUN {run_counter}/{total_tests}")
                print(f" START: ({s_lat}, {s_lon})")
                print(f" END:   ({e_lat}, {e_lon})")
                print(f"\n--------------------------------------------------------")

                update_grid_data(s_lat, s_lon, e_lat, e_lon)

                run_start = time.perf_counter()

                run_simulation()

                run_end = time.perf_counter()

                duration = run_end - run_start
                run_durations.append(duration)

                print(f">> Run {run_counter} completed in {duration:.2f} seconds ({duration / 60:.2f} mins)")
                
                run_counter += 1


    except KeyboardInterrupt:
        print("\nCtrl+C evoked, stopping sim...")
        stop_simulation()
    except Exception as err:
        print(f"\nCritical error: {err}")
        stop_simulation()
    finally:
        total_runs_completed = len(run_durations)
        end_time = datetime.now()
        if total_runs_completed > 0:
            total_duration = sum(run_durations)
            avg_duration = total_duration / total_runs_completed
            with open(SUMMARY_FILE, "w") as f:
                f.write(f"Simulation started at: {start_time.strftime(time_format)}\n")
                f.write(f"Simulation ended at: {end_time.strftime(time_format)}\n")
                f.write(f"Total runs completed: {total_runs_completed}\n")
                f.write(f"Total duration: {total_duration:.2f} seconds ({total_duration / 60:.2f} mins)\n")
                f.write(f"Average duration: {avg_duration:.2f} seconds ({avg_duration / 60:.2f} mins)\n")

                
            print(f"\nSaved run statistics to {SUMMARY_FILE}")
if __name__ == "__main__":
    main()