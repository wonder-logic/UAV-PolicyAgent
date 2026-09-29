## UAVGuard
Unmanned Aerial Vehicles (UAVs) are becoming increasingly common in commercial, recreational, and research applications. As drone usage continues to grow, ensuring compliance with aviation regulations established by the Federal Aviation Administration (FAA), as well as policies that may be imposed by local authorities and property owners within controlled airspace or restricted physical spaces, remains a significant challenge. This paper proposes UAVGuard, a multiagent AI-assisted drone authorization and mission evaluation framework designed to support collaborative decision-making for UAV flight requests. UAVGuard is composed of multiple interacting agents, including an AI Assistant Agent, a Knowledge Agent, and a Simulation Agent, which collectively evaluate drone mission feasibility and compliance constraints. The AI Assistant Agent processes user flight requests and retrieve relevant regulatory information through document retrieval and vector-based search techniques. The Knowledge Agent provides both static and dynamic operational data, including drone specifications, weather conditions, route information, and battery status, supporting the AI assistant agent for policy-based decision-making regarding flight authorization. The resulting decision is then communicated to the Simulation Agent for route generation and mission planning. Overall, UAVGuard aims to improve the explainability, consistency, and efficiency of drone compliance verification while demonstrating how cybersecurity access-control principles can be applied to autonomous drone operations.

## Quick Start

### Prerequisites

- Python 3.12 or later
- Git
- Node.js, only if you want to run the frontend tests

Clone the repository from GitHub and move into the project directory. Replace `<repository-url>` with the repository's GitHub URL:

```bash
git clone <repository-url>
cd UAV-PolicyAgent
```

### Windows PowerShell

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

### macOS or Linux

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
