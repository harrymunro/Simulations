# Machine Shop Simulation - Interactive Animation

An interactive, visually-rich animation of the classic SimPy Machine Shop simulation example.

## Overview

This animation brings the [SimPy Machine Shop example](https://simpy.readthedocs.io/en/latest/examples/machine_shop.html) to life with:

- **10 animated machines** with real-time progress bars
- **A moving repairman** who travels between machines and an "other jobs" station
- **Particle effects** - sparks when machines break down, smoke from broken machines, celebration effects when parts complete
- **Interactive controls** - adjust speed, pause/resume, manually break machines
- **Real-time statistics** - parts made, breakdowns, repairman utilization, per-machine performance charts

## The Simulation

The simulation models a machine shop with the following characteristics:

- **10 machines** continuously produce parts
- Each part takes ~10 minutes (normally distributed) to produce
- Machines break down randomly (exponential distribution, mean time to failure = 300 minutes)
- **One repairman** repairs broken machines (30 minutes per repair)
- The repairman also performs other jobs when no machines need repair
- Machine repairs **preempt** other jobs (machines have priority)

## Installation

```bash
pip install -r requirements.txt
```

## Running the Animation

```bash
python machine_shop_animation.py
```

## Controls

| Control | Action |
|---------|--------|
| Click on working machine | Cause manual breakdown |
| Speed slider | Adjust simulation speed (0.5x - 20x) |
| SPACE or Pause button | Pause/Resume simulation |
| R or Reset button | Reset simulation |
| Q or ESC | Quit |

## Visual Guide

### Machine States

- **Green (working)** - Machine is producing a part, progress bar shows completion
- **Red (flashing)** - Machine is broken, waiting for the repairman
- **Orange (repairing)** - Repairman is fixing the machine, progress bar shows repair status

### Statistics Panel

- **Simulation Time** - Days, hours, and minutes elapsed
- **Total Parts Made** - Sum of all parts produced
- **Total Breakdowns** - Sum of all machine failures
- **Repairman Utilization** - Percentage of time spent repairing vs. other jobs
- **Parts per Machine** - Bar chart comparing machine productivity

## Architecture

The animation uses:

- **SimPy** - Discrete-event simulation framework for the underlying simulation logic
- **Pygame** - Real-time rendering and user interaction
- **Particle System** - For visual effects (sparks, smoke, completion celebrations)

The simulation runs in real-time with configurable speed, synchronized with the visualization layer.

## Based On

This is an interactive visualization of the official SimPy Machine Shop example:
https://simpy.readthedocs.io/en/latest/examples/machine_shop.html
