# SimPy Entity Animation Simulation

A demonstration of using SimPy as a discrete event simulation engine while tracking and animating entity movement in 2D space.

## Features

- Uses SimPy for discrete event simulation
- Entities move between random waypoints at varying speeds
- Tracks entity positions over time
- Generates animated GIF output (mobile-friendly)
- Colorful trails showing entity movement history

## Requirements

- Python 3.11+
- UV package manager

## Installation

```bash
uv sync
```

## Running the Simulation

```bash
uv run python main.py
```

This will:
1. Run the simulation with 6 entities for 30 time units
2. Generate `entity_animation.gif` showing the entities moving

## Configuration

You can modify the simulation parameters in `main.py`:

```python
sim = EntitySimulation(
    num_entities=6,      # Number of moving entities
    world_size=100.0,    # Size of the 2D world
    sim_duration=30.0,   # Simulation duration in time units
    timestep=0.1,        # Time resolution for position recording
    seed=42              # Random seed for reproducibility
)
```
