"""
SimPy Entity Animation Simulation

Demonstrates using SimPy as a discrete event simulation engine while tracking
entity positions over time and animating their movement.

Entities move between waypoints in a 2D space, with the simulation recording
their positions at each timestep for visualization.
"""

import simpy
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from dataclasses import dataclass, field
from typing import Generator


@dataclass
class Position:
    """2D position with interpolation support."""
    x: float
    y: float

    def distance_to(self, other: "Position") -> float:
        return np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def interpolate(self, target: "Position", fraction: float) -> "Position":
        """Linearly interpolate between self and target."""
        return Position(
            x=self.x + (target.x - self.x) * fraction,
            y=self.y + (target.y - self.y) * fraction
        )


@dataclass
class Entity:
    """A moving entity in the simulation."""
    id: int
    position: Position
    speed: float
    color: str
    history: list[tuple[float, Position]] = field(default_factory=list)

    def record_position(self, time: float) -> None:
        """Record current position at given time."""
        self.history.append((time, Position(self.position.x, self.position.y)))


class EntitySimulation:
    """
    SimPy-based simulation of entities moving in 2D space.

    Entities move between randomly generated waypoints, with their positions
    recorded at each simulation timestep for later animation.
    """

    def __init__(
        self,
        num_entities: int = 5,
        world_size: float = 100.0,
        sim_duration: float = 50.0,
        timestep: float = 0.1,
        seed: int = 42
    ):
        self.num_entities = num_entities
        self.world_size = world_size
        self.sim_duration = sim_duration
        self.timestep = timestep
        self.rng = np.random.default_rng(seed)

        self.env = simpy.Environment()
        self.entities: list[Entity] = []

        # Color palette for entities
        self.colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00',
                       '#ffff33', '#a65628', '#f781bf', '#999999', '#66c2a5']

    def _create_entities(self) -> None:
        """Initialize entities at random starting positions."""
        for i in range(self.num_entities):
            pos = Position(
                x=self.rng.uniform(10, self.world_size - 10),
                y=self.rng.uniform(10, self.world_size - 10)
            )
            entity = Entity(
                id=i,
                position=pos,
                speed=self.rng.uniform(2.0, 8.0),
                color=self.colors[i % len(self.colors)]
            )
            entity.record_position(0.0)
            self.entities.append(entity)

    def _generate_waypoint(self) -> Position:
        """Generate a random waypoint within the world bounds."""
        return Position(
            x=self.rng.uniform(5, self.world_size - 5),
            y=self.rng.uniform(5, self.world_size - 5)
        )

    def _entity_movement_process(self, entity: Entity) -> Generator:
        """SimPy process for entity movement between waypoints."""
        while True:
            # Pick a new waypoint
            target = self._generate_waypoint()
            distance = entity.position.distance_to(target)
            travel_time = distance / entity.speed

            if travel_time < self.timestep:
                # Close enough, just move there
                entity.position = target
                entity.record_position(self.env.now)
                yield self.env.timeout(self.timestep)
                continue

            # Move towards target in timestep increments
            start_pos = Position(entity.position.x, entity.position.y)
            elapsed = 0.0

            while elapsed < travel_time:
                step = min(self.timestep, travel_time - elapsed)
                yield self.env.timeout(step)
                elapsed += step

                # Update position via interpolation
                fraction = elapsed / travel_time
                entity.position = start_pos.interpolate(target, fraction)
                entity.record_position(self.env.now)

    def _position_recorder_process(self) -> Generator:
        """Background process to ensure all positions are recorded at regular intervals."""
        while True:
            yield self.env.timeout(self.timestep)

    def run(self) -> None:
        """Run the simulation."""
        print(f"Initializing simulation with {self.num_entities} entities...")
        self._create_entities()

        # Start movement processes for each entity
        for entity in self.entities:
            self.env.process(self._entity_movement_process(entity))

        # Run simulation
        print(f"Running simulation for {self.sim_duration} time units...")
        self.env.run(until=self.sim_duration)
        print(f"Simulation complete. Recorded {len(self.entities[0].history)} positions per entity.")

    def get_positions_at_time(self, t: float) -> list[tuple[float, float, str]]:
        """Get all entity positions at a specific time."""
        positions = []
        for entity in self.entities:
            # Find closest recorded time
            for time, pos in entity.history:
                if time >= t:
                    positions.append((pos.x, pos.y, entity.color))
                    break
            else:
                # Use last known position
                if entity.history:
                    _, pos = entity.history[-1]
                    positions.append((pos.x, pos.y, entity.color))
        return positions


def create_animation(sim: EntitySimulation, output_file: str = "entity_animation.gif") -> None:
    """Create and save an animation of the simulation."""
    print("Creating animation...")

    fig, ax = plt.subplots(figsize=(8, 8), facecolor='#1a1a2e')
    ax.set_facecolor('#16213e')
    ax.set_xlim(0, sim.world_size)
    ax.set_ylim(0, sim.world_size)
    ax.set_aspect('equal')
    ax.set_title('SimPy Entity Movement Simulation', color='white', fontsize=14, pad=10)
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_color('#4a5568')

    # Grid
    ax.grid(True, alpha=0.2, color='white')

    # Initialize scatter plot and trail lines
    scatter = ax.scatter([], [], s=200, zorder=5, edgecolors='white', linewidth=2)
    trails = [ax.plot([], [], alpha=0.4, linewidth=2)[0] for _ in sim.entities]

    # Time display
    time_text = ax.text(
        0.02, 0.98, '', transform=ax.transAxes,
        color='white', fontsize=12, verticalalignment='top',
        fontfamily='monospace'
    )

    # Collect all times
    all_times = sorted(set(t for entity in sim.entities for t, _ in entity.history))

    def init():
        scatter.set_offsets(np.empty((0, 2)))
        for trail in trails:
            trail.set_data([], [])
        time_text.set_text('')
        return [scatter, time_text] + trails

    def animate(frame):
        if frame >= len(all_times):
            return [scatter, time_text] + trails

        current_time = all_times[frame]
        positions = sim.get_positions_at_time(current_time)

        if positions:
            xy = np.array([(p[0], p[1]) for p in positions])
            colors = [p[2] for p in positions]
            scatter.set_offsets(xy)
            scatter.set_facecolors(colors)

        # Update trails (show last N positions)
        trail_length = min(50, frame + 1)
        for i, entity in enumerate(sim.entities):
            if frame < len(entity.history):
                start_idx = max(0, frame - trail_length)
                trail_positions = entity.history[start_idx:frame + 1]
                xs = [p.x for _, p in trail_positions]
                ys = [p.y for _, p in trail_positions]
                trails[i].set_data(xs, ys)
                trails[i].set_color(entity.color)

        time_text.set_text(f'Time: {current_time:.1f}')
        return [scatter, time_text] + trails

    # Create animation - use fewer frames for faster GIF
    step = max(1, len(all_times) // 200)  # Limit to ~200 frames
    frame_indices = range(0, len(all_times), step)

    anim = animation.FuncAnimation(
        fig, animate, init_func=init,
        frames=len(list(frame_indices)),
        interval=50, blit=True
    )

    # Reset frame counter for actual animation
    def animate_stepped(frame):
        return animate(frame * step)

    anim = animation.FuncAnimation(
        fig, animate_stepped, init_func=init,
        frames=len(all_times) // step,
        interval=50, blit=True
    )

    # Save as GIF (mobile-friendly)
    print(f"Saving animation to {output_file}...")
    anim.save(output_file, writer='pillow', fps=20, dpi=100)
    print(f"Animation saved! View {output_file} on any device.")

    plt.close()


def main():
    """Run the entity animation simulation."""
    print("=" * 60)
    print("SimPy Entity Animation Simulation")
    print("=" * 60)
    print()

    # Create and run simulation
    sim = EntitySimulation(
        num_entities=6,
        world_size=100.0,
        sim_duration=30.0,
        timestep=0.1,
        seed=42
    )
    sim.run()

    print()

    # Create animation
    create_animation(sim, "entity_animation.gif")

    print()
    print("=" * 60)
    print("Simulation complete!")
    print("The GIF can be viewed on mobile or any device.")
    print("=" * 60)


if __name__ == "__main__":
    main()
