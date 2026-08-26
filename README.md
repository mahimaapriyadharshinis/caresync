# CARESync

**Adaptive SDN Framework for Multi-Hospital Emergency Resource Synchronization Under Communication Constraints**

CARESync is a working implementation of a Software-Defined Networking framework that synchronizes emergency resource data (ICU beds, ER occupancy, ventilators) across multiple hospitals. Instead of every hospital broadcasting continuously (high bandwidth cost) or on a fixed timer (stale data during emergencies), CARESync scores each resource change for urgency and network congestion, then has an SDN controller route that update with a priority matched to how urgent it actually is.

Built for BCSE308L, Computer Networks, Vellore Institute of Technology.

| | |
|---|---|
| Team | Triple Protocol |
| Members | Bhavya Chopra (24BCE0540), Sadaf Shakoor (24BCB0147), S Mahimaa Priyadharshini (24BCE0411) |
| Guide | Prof. Yoganand S |
| Course | BCSE308L, Computer Networks |

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Architecture](#architecture)
- [Results](#results)
- [Repository Structure](#repository-structure)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Running the System](#running-the-system)
- [Running the Evaluation](#running-the-evaluation)
- [Testing](#testing)
- [Environment Notes](#environment-notes)
- [Project Status](#project-status)
- [References](#references)

---

## Problem Statement

During large-scale emergencies, hospitals need to continuously exchange critical resource information. If Hospital A runs out of ICU beds and a nearby hospital's ambulance dispatch system learns about it five minutes late, that ambulance is already heading to the wrong hospital.

Existing synchronization strategies fail in opposite directions:

- **Continuous synchronization** — every hospital broadcasts every update. Data stays fresh, but bandwidth consumption and network congestion scale with every single change, most of which are not urgent.
- **Periodic synchronization** — hospitals broadcast their state on a fixed timer. Bandwidth cost is predictable, but a critical update (a resource hitting zero) can sit stale for the length of an entire interval before anyone else learns about it.

**Research question:** how can multiple hospitals adaptively synchronize emergency resource information while minimizing communication overhead and ensuring timely decision-making?

CARESync's answer: separate the question of *whether something changed* from the question of *how urgently it needs to be known elsewhere*, and let an SDN controller act on that distinction directly at the network layer.

## Architecture

```
INPUT: DATA COLLECTION
  Hospitals A, B, C — resource monitors reporting live ICU/ER/ventilator counts
        |
        v
PROCESSING: ADAPTIVE SYNC ENGINE
  Evaluates resource-change magnitude, current network congestion, and urgency
        |
        v
SDN CONTROLLER
  Translates the engine's decision (WHEN, WHO, WHAT, HOW) into OpenFlow flow rules
        |
        v
OUTPUT: NETWORK EXECUTION
  OpenFlow switches route packets with a priority matched to urgency
```

Every update is classified into one of three tiers:

| Tier | Trigger | Action |
|---|---|---|
| CRITICAL | Resource hits zero, or a large drop | Delivered immediately, on a high-priority OpenFlow flow rule |
| CONGESTED | A meaningful change, but the network is currently busy | Held briefly, delivered once congestion clears |
| ROUTINE | A small, non-urgent change | Batched into the next periodic sync interval |

This decision is made once, in `sync_engine/`, and consumed identically by the live backend and by the offline evaluation harness, so the same logic that runs against Mininet is what the comparison numbers below are measured against.

## Results

The evaluation harness (`evaluation/`) replays one synthetic 500-event trace of ICU/ER/ventilator changes through all three strategies — continuous, periodic, and adaptive — and measures communication overhead (network messages sent, including broadcast fan-out to the other hospitals) and staleness (seconds between a resource actually changing and other hospitals learning about it).

| Strategy | Messages sent | Avg staleness | Staleness on critical events |
|---|---|---|---|
| Continuous | 1000 | 0.0 s | 0.0 s |
| Periodic (5 min interval) | 660 | 150.6 s | 129.0 s |
| **Adaptive (CARESync)** | 816 | 84.2 s | **~0.0 s** |

Adaptive sends fewer messages than continuous broadcasting, and — unlike periodic sync — never lets a critical update (an ICU count hitting zero) sit stale waiting for the next interval. This is the project's core claim, and it is asserted by automated tests (`tests/test_evaluation.py`) against arbitrarily seeded traces, not just this one run.

The same numbers are visualized in a provisioned Grafana dashboard (`dashboards/provisioning/dashboards/json/caresync-comparison.json`) reading live from the backend's `/evaluation/latest` endpoint.

## Repository Structure

```
caresync/
  sync_engine/           Adaptive Sync Engine — urgency/congestion scoring, the project's
                          core algorithmic contribution. Pure Python, no network dependency.
    models.py               ResourceUpdate, ScoreResult, SyncTier data structures
    scorer.py                magnitude and urgency computation
    policy.py                the CRITICAL / CONGESTED / ROUTINE decision rule
    engine.py                orchestrates scorer + policy into one entry point

  simulation/             Synthetic resource-event generation
    event_generator.py      Poisson-arrival ICU/ER/ventilator event generator

  backend/                FastAPI service — the northbound API hospitals report through
    main.py                  HTTP endpoints
    storage.py                MongoDB-backed (or in-memory) hospital state and decision log
    congestion.py             pluggable network-congestion signal
    controller_client.py      REST client that notifies the SDN controller of CRITICAL updates
    evaluation_store.py       read access to stored evaluation runs

  controller/             SDN controller (os-ken, the maintained fork of Ryu)
    flow_manager.py          L2 learning switch plus priority-aware flow installation
    congestion_monitor.py     polls OpenFlow port statistics for a live congestion reading
    rest_api.py               REST hook the backend calls to mark a host's flow CRITICAL
    run.py                    launches all three controller apps together

  topology/               Mininet network topology
    hospital_net.py          3 hospitals + 2 ambulances on one switch

  evaluation/              Phase 5 comparison harness
    strategies.py             continuous / periodic / adaptive strategy simulation
    network_conditions.py     synthetic congestion signal used by the adaptive strategy
    run_comparison.py         CLI entry point; can persist results to MongoDB

  docker/                 Container definitions
    Dockerfile.hospital       backend + MongoDB client image
    Dockerfile.mininet        Mininet + Open vSwitch + os-ken image
    start-ovs.sh               brings up Open vSwitch in userspace mode

  dashboards/             Grafana provisioning
    provisioning/datasources/   Infinity datasource pointed at the backend
    provisioning/dashboards/    the comparison dashboard definition

  docs/
    environment-notes.md      the two environment-forced deviations from the proposal, explained

  tests/                  pytest suite covering every module above (34 tests)
  deployment_config.py    shared hospital-id -> MAC address mapping (backend and topology)
  docker-compose.yml      backend + MongoDB + Grafana, one command
  requirements.txt        Python dependencies for the backend/evaluation half
```

## Technology Stack

| Tool | Role |
|---|---|
| Python | Core implementation language throughout |
| FastAPI | Backend HTTP service hospitals report resource updates through |
| MongoDB | Persists hospital state, sync decisions, and evaluation runs |
| NetworkX | Network topology / graph utilities |
| Mininet | Emulates the multi-hospital network topology |
| os-ken | SDN controller framework (maintained fork of Ryu — see [Environment Notes](#environment-notes)) |
| Open vSwitch | OpenFlow switches inside the Mininet topology |
| Docker / Docker Compose | Containerizes the backend, MongoDB, and Grafana |
| Grafana | Visualizes the strategy-comparison results |
| pytest | Test suite (34 tests across every module) |

## Getting Started

The Mininet/Open vSwitch half of this project needs a Linux kernel with network-namespace support. It was developed and verified on Windows via **WSL2 (Ubuntu 22.04)** with Docker Desktop's WSL2 integration; a native Linux machine works identically.

### Prerequisites

- WSL2 with an Ubuntu distribution (or a native Linux machine)
- Docker Desktop (or Docker Engine on Linux) with the WSL2 integration enabled
- Python 3.10+

### Clone and set up the Python environment

```bash
git clone https://github.com/mahimaapriyadharshinis/caresync.git
cd caresync

python3 -m pip install --user virtualenv
python3 -m virtualenv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install pytest httpx  # test-only dependencies
```

## Running the System

### Backend + MongoDB + Grafana (Docker Compose)

The simplest way to see the backend working end to end:

```bash
docker compose up -d --build
```

This starts three services:

- `backend` — the FastAPI app, on `http://localhost:8000`
- `mongo` — MongoDB, on `localhost:27017`
- `grafana` — on `http://localhost:3000` (default login `admin` / `admin`), with the comparison dashboard already provisioned

Try it:

```bash
curl -X POST localhost:8000/hospitals/hospA/update \
  -H "Content-Type: application/json" \
  -d '{"resource": "icu_beds", "new_value": 3, "capacity": 10}'

curl -X POST localhost:8000/hospitals/hospA/update \
  -H "Content-Type: application/json" \
  -d '{"resource": "icu_beds", "new_value": 0, "capacity": 10}'
```

The second call should return `"tier": "critical"`.

### Mininet topology and SDN controller

The network half runs in a separate, privileged container (Mininet needs kernel-level access that a standard Compose service does not grant):

```bash
docker build -f docker/Dockerfile.mininet -t caresync-mininet .
docker run -d --privileged --name caresync-net caresync-mininet

# start the controller (flow manager, congestion monitor, REST hook)
docker exec -d caresync-net bash -lc "cd /caresync && python3 controller/run.py"

# bring up the topology and test connectivity
docker exec caresync-net bash -lc "cd /caresync && python3 -c \"
from topology.hospital_net import run
run()
\""
```

`net.pingAll()` should report `0% dropped`.

To connect the backend to this running controller, set `CONTROLLER_URL=http://caresync-net:8080` on the backend service (already the default in `docker-compose.yml`) and put both containers on the same Docker network:

```bash
docker network connect hospital_default caresync-net
```

## Running the Evaluation

To reproduce the comparison numbers in [Results](#results):

```bash
source .venv/bin/activate
python -m evaluation.run_comparison --events 500 --seed 1 --mongo-url mongodb://localhost:27017
```

Omit `--mongo-url` to print the comparison without persisting it. With it set, the result becomes visible at `GET /evaluation/latest` on the backend, and on the Grafana dashboard.

## Testing

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

34 tests, covering the Adaptive Sync Engine's decision logic, the synthetic event generator, the FastAPI backend, the controller REST client, and the strategy-comparison harness — including tests that assert the project's actual empirical claims (for example, that adaptive keeps critical-event staleness near zero while periodic does not).

## Environment Notes

Two implementation choices deviate from a literal reading of the original proposal, both forced by the development environment rather than chosen for convenience. Full detail in `docs/environment-notes.md`; summary:

- **os-ken instead of Ryu.** Plain `pip install ryu` fails on any current Python/setuptools toolchain — Ryu's packaging depends on `setuptools.command.easy_install`, which modern setuptools no longer ships. os-ken is the actively maintained fork of Ryu (OpenStack-maintained after upstream Ryu went inactive), with an identical architecture and API shape; only the import path changes (`os_ken.*` instead of `ryu.*`).
- **Open vSwitch userspace datapath instead of kernel.** The WSL2 kernel does not ship the `openvswitch.ko` kernel module. Every switch in this project runs OVS's userspace ("netdev") datapath instead, which needs no kernel module and is functionally equivalent for this project's purposes. On a machine with the kernel module available, dropping `datapath="user"` in `topology/hospital_net.py` switches back to the default kernel datapath with no other code changes required.

## Project Status

| Phase (per the original 14-week plan) | Status |
|---|---|
| 1. Literature review | Complete |
| 2. Dataset / environment setup | Complete — Mininet topology verified, synthetic event generator built |
| 3. Algorithm design | Complete — Adaptive Sync Engine, thresholds tuned and tested |
| 4. Development | Complete — backend, controller, and their integration all verified live |
| 5. Testing and evaluation | Complete — comparison harness, Grafana dashboard, 34 passing tests |
| 6. Paper writing | Not started |

Not implemented: the Flower federated-learning extension (marked a stretch goal in the original proposal), and per-hospital containerized Mininet nodes for large-scale simulation (the current setup uses one multi-tenant backend service rather than N separate hospital containers).

## References

1. Kreutz, D., et al. (2015). "Software-defined networking: A comprehensive survey." *Proceedings of the IEEE.*
2. A. M. H. et al. (2020). "QoS-Aware Routing in SDN-based IoT Networks for Healthcare Applications." *IEEE Internet of Things Journal.*
3. Mininet Documentation and Research Ecosystem — http://mininet.org
4. Ryu / os-ken SDN Framework Documentation — https://ryu.readthedocs.io/, https://docs.openstack.org/os-ken/
5. Open Networking Foundation. "OpenFlow Switch Specification."
