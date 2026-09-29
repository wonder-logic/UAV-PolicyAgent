## UAVGuard
Unmanned Aerial Vehicles (UAVs) are becoming increasingly common in commercial, recreational, and research applications. As drone usage continues to grow, ensuring compliance with aviation regulations established by the Federal Aviation Administration (FAA), as well as policies that may be imposed by local authorities and property owners within controlled airspace or restricted physical spaces, remains a significant challenge. This paper proposes UAVGuard, a multiagent AI-assisted drone authorization and mission evaluation framework designed to support collaborative decision-making for UAV flight requests. UAVGuard is composed of multiple interacting agents, including an AI Assistant Agent, a Knowledge Agent, and a Simulation Agent, which collectively evaluate drone mission feasibility and compliance constraints. The AI Assistant Agent processes user flight requests and retrieve relevant regulatory information through document retrieval and vector-based search techniques. The Knowledge Agent provides both static and dynamic operational data, including drone specifications, weather conditions, route information, and battery status, supporting the AI assistant agent for policy-based decision-making regarding flight authorization. The resulting decision is then communicated to the Simulation Agent for route generation and mission planning. Overall, UAVGuard aims to improve the explainability, consistency, and efficiency of drone compliance verification while demonstrating how cybersecurity access-control principles can be applied to autonomous drone operations.

## Policy Agent

### Quick Start

#### Prerequisites

- Python 3.12 or later
- Git
- Node.js, only if you want to run the frontend tests

Clone the repository from GitHub and move into the project directory. Replace `<repository-url>` with the repository's GitHub URL:

```bash
git clone <repository-url>
cd UAV-PolicyAgent
cd policy-agent
```

#### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -e ".[dev]"
Copy-Item .env.example .env
py -m alembic upgrade head
py scripts\run_api.py
```

If PowerShell prevents virtual-environment activation, run this once in the current PowerShell session and activate again:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

#### macOS or Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
python -m alembic upgrade head
python scripts/run_api.py
```

When the server starts, keep that terminal open and visit:

- Application: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/health

The FastAPI server serves the frontend, so no separate frontend server is required. Local development uses mock integrations by default and does not require API keys.

## Run Tests

With the virtual environment activated, run the backend tests.

Windows PowerShell:

```powershell
py -m pytest -q
```

macOS or Linux:

```bash
python -m pytest -q
```

To run the frontend tests, use:

```bash
node --test frontend-tests/app.test.mjs
```

Stop the running server with `Ctrl+C`.

## Run the Knowledge Agent

The `knowledge-agent` folder is a separate Streamlit application. It reads the
mission request from `ai_request.json`, collects drone, location, weather, and
terrain information, and writes result files such as `mission_context.json`
and `flight_feasibility.json`.

### Knowledge Agent prerequisites

- Python 3.12 or later
- An Ollama installation with the `llama3.2` model
- Internet access for geocoding, weather, map, and manufacturer lookups
- A valid Geoapify API key in `knowledge-agent/config.py`

Install the Python dependencies from the repository root. On Windows, use the
virtual environment created for the policy agent:

```powershell
.\policy-agent\.venv\Scripts\Activate.ps1
py -m pip install streamlit requests geopy timezonefinder beautifulsoup4 ddgs ollama
ollama pull llama3.2
cd knowledge-agent
```

On macOS or Linux:

```bash
source policy-agent/.venv/bin/activate
python -m pip install streamlit requests geopy timezonefinder beautifulsoup4 ddgs ollama
ollama pull llama3.2
cd knowledge-agent
```

### Run the interactive application

Start the Streamlit interface from inside the `knowledge-agent` directory:

```bash
streamlit run app.py
```

Open the URL printed by Streamlit, usually http://localhost:8501. Enter a
drone, battery percentage, start location, and destination, then select
**Analyze Mission**.

### Run the knowledge-agent script

To run the non-UI processing flow using the values in `ai_request.json`:

```bash
python knowledge_agent.py
```

This builds `mission_context.json`. Route evaluation also requires a
`simulator_response.json` file containing a distance, for example:

```json
{
	"distance_miles": 2
}
```

After that file is available, run `python knowledge_agent.py` again to write
`flight_feasibility.json` and `can_fly.json`.

### Files that must be present

The current `knowledge-agent` source imports or opens these files, but they are
not included in this checkout:

- `weather_lookup.py`
- `opendronelist.json`
- `tamucc_logo.png`

Add those files before running the application. The JSON files already present
in the folder are input, cache, or generated result files; they are not Python
programs and should not be executed individually.

## Run the Simulation Agent

The `simulation-agent` folder contains the grid/path planner and the optional
Gazebo and ArduPilot SITL flight simulation. Run these commands from the
repository root after activating the Python virtual environment:

```bash
cd simulation-agent
python -m pip install networkx mavsdk matplotlib numpy pymavlink
```

### Run the planner without Gazebo

The planner can calculate a route and create `simulator_response.json` without
starting a simulated drone:

```bash
python processing_data.py
python pathfinder.py
```

The start and destination coordinates are configured in `grid_data.py`. The
pathfinder writes the calculated route distance to `simulator_response.json`.

To display the grid, use:

```bash
python visualize_zones.py
```

The visualization expects a MAVLink heartbeat on UDP port `14551` unless the
MAVLink connection code in `visualize_zones.py` is changed for standalone grid
testing.

### Run the full flight simulation

The full simulation requires Linux or WSL with a graphical environment and the
following installed and configured outside this repository:

- Gazebo Sim with the ArduPilot Gazebo plugin and `~/ardupilot_gazebo`
- ArduPilot SITL and `sim_vehicle.py`
- MAVProxy
- `tmux`
- A MAVSDK-compatible simulated vehicle listening on UDP port `14552`

The intended components are:

1. `scripts/1_gazebo.sh` starts Gazebo.
2. `scripts/2_ardupilot.sh` starts ArduCopter SITL.
3. `scripts/4_zones.sh` starts the zone visualization.
4. `scripts/5_fly.sh` runs `fly.py` through MAVSDK.

The shell scripts use Linux commands and are not supported directly from
Windows PowerShell. Before using `master_launch.sh`, change its `SCRIPTS_DIR`
value from `"$MAIN_DIR/SCRIPTS"` to `"$MAIN_DIR/scripts"`; the repository
directory is lowercase. Then run:

```bash
cd simulation-agent
chmod +x master_launch.sh stop_sim.sh scripts/*.sh
./master_launch.sh
```

Stop the full stack with:

```bash
./stop_sim.sh
```

To run the flight script by itself, ensure ArduPilot SITL is already running
and `can_fly.json` contains `{"allowed_to_fly": 1}`:

```bash
python fly.py
```

The flight script writes telemetry to `flight_records.txt` and coordinate data
to `drone_coords.txt`. The batch runner `run_all_tests_w_time.py` launches
multiple full simulations and should only be used after the full stack works
once; it modifies `grid_data.py` and requires the Linux shell scripts.
