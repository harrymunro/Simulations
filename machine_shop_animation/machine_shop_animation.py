"""
Interactive Machine Shop Simulation Animation

An interactive visualization of the SimPy Machine Shop example featuring:
- 10 animated machines with progress bars
- A repairman that moves between machines
- Breakdown effects (sparks and smoke)
- Interactive controls (speed, pause, click-to-break)
- Real-time statistics dashboard

Based on: https://simpy.readthedocs.io/en/latest/examples/machine_shop.html

Controls:
- Click on a working machine to cause a manual breakdown
- Use speed slider to adjust simulation speed (1x - 20x)
- Press SPACE or click Pause to pause/resume
- Press R or click Reset to restart simulation
- Press Q or ESC to quit
"""

import pygame
import random
import math
import simpy
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from collections import deque
import threading
import time

# Initialize Pygame
pygame.init()
pygame.font.init()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Window settings
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
FPS = 60

# Simulation parameters (scaled down for visual appeal)
RANDOM_SEED = 42
PT_MEAN = 10.0          # Avg processing time in sim-minutes
PT_SIGMA = 2.0          # Sigma of processing time
MTTF = 300.0            # Mean time to failure in sim-minutes
BREAK_MEAN = 1 / MTTF   # Param for exponential distribution
REPAIR_TIME = 30.0      # Time to repair in sim-minutes
JOB_DURATION = 30.0     # Duration of other jobs in sim-minutes
NUM_MACHINES = 10       # Number of machines

# Visual scaling: 1 sim-minute = this many real seconds at 1x speed
SIM_MINUTE_TO_SECONDS = 0.1

# Colors
COLORS = {
    'background': (30, 35, 45),
    'panel': (45, 52, 65),
    'panel_light': (55, 65, 80),
    'text': (220, 225, 235),
    'text_dim': (140, 150, 165),
    'accent': (100, 180, 255),
    'success': (80, 200, 120),
    'warning': (255, 180, 60),
    'danger': (255, 90, 90),
    'machine_working': (70, 160, 100),
    'machine_broken': (200, 60, 60),
    'machine_repair': (230, 160, 50),
    'machine_idle': (100, 110, 125),
    'progress_bg': (60, 70, 85),
    'repairman': (100, 180, 255),
    'spark': (255, 200, 50),
    'smoke': (80, 80, 80),
}

# ============================================================================
# PARTICLE SYSTEM
# ============================================================================

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: Tuple[int, int, int]
    size: float
    particle_type: str  # 'spark', 'smoke', 'complete'

class ParticleSystem:
    def __init__(self):
        self.particles: List[Particle] = []

    def emit_sparks(self, x: float, y: float, count: int = 15):
        """Emit spark particles for machine breakdown"""
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 150)
            self.particles.append(Particle(
                x=x + random.uniform(-10, 10),
                y=y + random.uniform(-10, 10),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed - 50,
                life=random.uniform(0.3, 0.8),
                max_life=0.8,
                color=COLORS['spark'],
                size=random.uniform(2, 5),
                particle_type='spark'
            ))

    def emit_smoke(self, x: float, y: float, count: int = 3):
        """Emit smoke particles for broken machine"""
        for _ in range(count):
            self.particles.append(Particle(
                x=x + random.uniform(-20, 20),
                y=y,
                vx=random.uniform(-10, 10),
                vy=random.uniform(-40, -20),
                life=random.uniform(1.0, 2.0),
                max_life=2.0,
                color=COLORS['smoke'],
                size=random.uniform(8, 15),
                particle_type='smoke'
            ))

    def emit_complete(self, x: float, y: float, count: int = 8):
        """Emit celebration particles for part completion"""
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(30, 80)
            self.particles.append(Particle(
                x=x,
                y=y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=random.uniform(0.5, 1.0),
                max_life=1.0,
                color=COLORS['success'],
                size=random.uniform(3, 6),
                particle_type='complete'
            ))

    def update(self, dt: float):
        """Update all particles"""
        for particle in self.particles[:]:
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.life -= dt

            if particle.particle_type == 'spark':
                particle.vy += 200 * dt  # gravity
            elif particle.particle_type == 'smoke':
                particle.size += 5 * dt  # expand
                particle.vx *= 0.98  # slow down

            if particle.life <= 0:
                self.particles.remove(particle)

    def draw(self, screen):
        """Draw all particles"""
        for particle in self.particles:
            alpha = int(255 * (particle.life / particle.max_life))
            color = (*particle.color[:3], alpha)

            if particle.particle_type == 'smoke':
                # Draw smoke as circle with transparency
                surf = pygame.Surface((int(particle.size * 2), int(particle.size * 2)), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*COLORS['smoke'], alpha // 2),
                                   (int(particle.size), int(particle.size)), int(particle.size))
                screen.blit(surf, (int(particle.x - particle.size), int(particle.y - particle.size)))
            else:
                # Draw spark/complete as small circles
                pygame.draw.circle(screen, particle.color[:3],
                                   (int(particle.x), int(particle.y)), int(particle.size))


# ============================================================================
# MACHINE STATE
# ============================================================================

class MachineState(Enum):
    WORKING = "working"
    BROKEN = "broken"
    BEING_REPAIRED = "being_repaired"
    WAITING_FOR_REPAIR = "waiting_for_repair"


@dataclass
class MachineVisual:
    """Visual state of a machine for animation"""
    id: int
    x: float
    y: float
    width: float = 120
    height: float = 140
    state: MachineState = MachineState.WORKING
    parts_made: int = 0
    breakdowns: int = 0
    work_progress: float = 0.0  # 0.0 to 1.0
    repair_progress: float = 0.0  # 0.0 to 1.0
    work_time_remaining: float = 0.0
    repair_time_remaining: float = 0.0
    work_time_total: float = 0.0
    hovered: bool = False
    flash_timer: float = 0.0


# ============================================================================
# REPAIRMAN VISUAL
# ============================================================================

@dataclass
class RepairmanVisual:
    """Visual state of the repairman"""
    x: float
    y: float
    target_x: float
    target_y: float
    target_machine: Optional[int] = None
    doing_other_job: bool = True
    other_job_progress: float = 0.0
    repair_count: int = 0
    time_repairing: float = 0.0
    time_other_jobs: float = 0.0
    animation_frame: float = 0.0


# ============================================================================
# SIMPY SIMULATION WITH EVENT TRACKING
# ============================================================================

class MachineShopSimulation:
    """SimPy-based machine shop simulation with event tracking for visualization"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset the simulation"""
        random.seed(RANDOM_SEED)
        self.env = simpy.Environment()
        self.repairman = simpy.PreemptiveResource(self.env, capacity=1)

        # Create machines
        self.machines: List['SimMachine'] = []
        for i in range(NUM_MACHINES):
            machine = SimMachine(self.env, i, self.repairman, self)
            self.machines.append(machine)

        # Start repairman's other jobs
        self.env.process(self._other_jobs())

        # Event tracking
        self.events = deque(maxlen=1000)
        self.repairman_target: Optional[int] = None
        self.repairman_doing_other_job = True
        self.paused = False
        self.sim_time = 0.0

    def _time_per_part(self):
        """Return actual processing time for a concrete part"""
        return max(1.0, random.normalvariate(PT_MEAN, PT_SIGMA))

    def _time_to_failure(self):
        """Return time until next failure for a machine"""
        return random.expovariate(BREAK_MEAN)

    def _other_jobs(self):
        """The repairman's other (unimportant) job"""
        while True:
            done_in = JOB_DURATION
            while done_in > 0:
                with self.repairman.request(priority=2) as req:
                    yield req
                    self.repairman_doing_other_job = True
                    self.repairman_target = None
                    try:
                        start = self.env.now
                        yield self.env.timeout(done_in)
                        done_in = 0
                    except simpy.Interrupt:
                        done_in -= self.env.now - start
                        self.repairman_doing_other_job = False

    def step(self, duration: float):
        """Step the simulation forward by duration sim-minutes"""
        if not self.paused:
            target = self.env.now + duration
            self.env.run(until=target)
            self.sim_time = self.env.now


class SimMachine:
    """A machine in the simulation"""

    def __init__(self, env: simpy.Environment, id: int, repairman: simpy.PreemptiveResource, shop: MachineShopSimulation):
        self.env = env
        self.id = id
        self.repairman = repairman
        self.shop = shop

        self.parts_made = 0
        self.breakdowns = 0
        self.broken = False
        self.being_repaired = False
        self.work_remaining = 0.0
        self.work_total = 0.0
        self.repair_remaining = 0.0

        # Start processes
        self.process = env.process(self._working())
        env.process(self._break_machine())

    def _working(self):
        """Produce parts as long as the simulation runs"""
        while True:
            # Start making a new part
            done_in = self.shop._time_per_part()
            self.work_total = done_in
            self.work_remaining = done_in

            while done_in > 0:
                try:
                    start = self.env.now
                    yield self.env.timeout(done_in)
                    done_in = 0
                    self.work_remaining = 0
                except simpy.Interrupt:
                    self.broken = True
                    self.breakdowns += 1
                    done_in -= self.env.now - start
                    self.work_remaining = done_in

                    # Request repairman
                    with self.repairman.request(priority=1) as req:
                        yield req
                        self.being_repaired = True
                        self.shop.repairman_target = self.id
                        self.shop.repairman_doing_other_job = False
                        self.repair_remaining = REPAIR_TIME
                        yield self.env.timeout(REPAIR_TIME)
                        self.repair_remaining = 0
                        self.being_repaired = False

                    self.broken = False

            # Part is done
            self.parts_made += 1

    def _break_machine(self):
        """Break the machine periodically"""
        while True:
            yield self.env.timeout(self.shop._time_to_failure())
            if not self.broken:
                self.process.interrupt()

    def force_break(self):
        """Force a breakdown (called from UI)"""
        if not self.broken:
            self.process.interrupt()


# ============================================================================
# UI COMPONENTS
# ============================================================================

class Button:
    def __init__(self, x, y, width, height, text, color=COLORS['panel_light'],
                 hover_color=COLORS['accent'], text_color=COLORS['text']):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.hovered = False
        self.font = pygame.font.SysFont('Arial', 16, bold=True)

    def draw(self, screen):
        color = self.hover_color if self.hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, COLORS['text_dim'], self.rect, 2, border_radius=8)

        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False


class Slider:
    def __init__(self, x, y, width, min_val, max_val, initial_val, label):
        self.x = x
        self.y = y
        self.width = width
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.label = label
        self.dragging = False
        self.font = pygame.font.SysFont('Arial', 14)
        self.label_font = pygame.font.SysFont('Arial', 14, bold=True)

    def draw(self, screen):
        # Label
        label_surf = self.label_font.render(self.label, True, COLORS['text'])
        screen.blit(label_surf, (self.x, self.y - 20))

        # Track
        track_rect = pygame.Rect(self.x, self.y + 8, self.width, 6)
        pygame.draw.rect(screen, COLORS['progress_bg'], track_rect, border_radius=3)

        # Filled portion
        fill_width = int((self.value - self.min_val) / (self.max_val - self.min_val) * self.width)
        fill_rect = pygame.Rect(self.x, self.y + 8, fill_width, 6)
        pygame.draw.rect(screen, COLORS['accent'], fill_rect, border_radius=3)

        # Handle
        handle_x = self.x + fill_width
        pygame.draw.circle(screen, COLORS['text'], (handle_x, self.y + 11), 10)
        pygame.draw.circle(screen, COLORS['accent'], (handle_x, self.y + 11), 7)

        # Value display
        value_text = f"{self.value:.1f}x"
        value_surf = self.font.render(value_text, True, COLORS['text'])
        screen.blit(value_surf, (self.x + self.width + 10, self.y + 2))

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            handle_x = self.x + int((self.value - self.min_val) / (self.max_val - self.min_val) * self.width)
            if abs(event.pos[0] - handle_x) < 15 and abs(event.pos[1] - (self.y + 11)) < 15:
                self.dragging = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = event.pos[0] - self.x
            rel_x = max(0, min(self.width, rel_x))
            self.value = self.min_val + (rel_x / self.width) * (self.max_val - self.min_val)
            return True
        return False


# ============================================================================
# MAIN ANIMATION CLASS
# ============================================================================

class MachineShopAnimation:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Machine Shop Simulation - Interactive Animation")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_large = pygame.font.SysFont('Arial', 28, bold=True)
        self.font_medium = pygame.font.SysFont('Arial', 18, bold=True)
        self.font_small = pygame.font.SysFont('Arial', 14)
        self.font_tiny = pygame.font.SysFont('Arial', 12)

        # Simulation
        self.simulation = MachineShopSimulation()

        # Particle system
        self.particles = ParticleSystem()

        # Create machine visuals
        self.machine_visuals = self._create_machine_layout()

        # Repairman visual
        self.repairman = RepairmanVisual(
            x=900, y=700,
            target_x=900, target_y=700
        )

        # UI components
        self.speed_slider = Slider(1050, 150, 200, 0.5, 20.0, 1.0, "Simulation Speed")
        self.pause_button = Button(1050, 200, 100, 40, "PAUSE")
        self.reset_button = Button(1160, 200, 100, 40, "RESET")

        # State
        self.running = True
        self.speed = 1.0
        self.last_machine_states = {}

    def _create_machine_layout(self) -> List[MachineVisual]:
        """Create machine visual objects in a grid layout"""
        machines = []
        start_x = 80
        start_y = 100
        spacing_x = 160
        spacing_y = 180

        for i in range(NUM_MACHINES):
            row = i // 5
            col = i % 5
            x = start_x + col * spacing_x
            y = start_y + row * spacing_y
            machines.append(MachineVisual(id=i, x=x, y=y))

        return machines

    def _update_machine_visuals(self, dt: float):
        """Sync machine visuals with simulation state"""
        for i, machine in enumerate(self.simulation.machines):
            visual = self.machine_visuals[i]

            # Check for state changes
            old_state = self.last_machine_states.get(i)

            if machine.broken and machine.being_repaired:
                new_state = MachineState.BEING_REPAIRED
                visual.repair_progress = 1.0 - (machine.repair_remaining / REPAIR_TIME) if REPAIR_TIME > 0 else 1.0
            elif machine.broken:
                new_state = MachineState.WAITING_FOR_REPAIR
                visual.flash_timer += dt * 5
            else:
                new_state = MachineState.WORKING
                if machine.work_total > 0:
                    visual.work_progress = 1.0 - (machine.work_remaining / machine.work_total)
                else:
                    visual.work_progress = 0.0

            # Emit particles on state change
            if old_state != new_state:
                if new_state == MachineState.WAITING_FOR_REPAIR and old_state == MachineState.WORKING:
                    # Machine just broke - emit sparks
                    self.particles.emit_sparks(visual.x + visual.width/2, visual.y + 30)
                elif new_state == MachineState.WORKING and old_state in [MachineState.BEING_REPAIRED, MachineState.WAITING_FOR_REPAIR]:
                    # Machine was just repaired
                    pass

            # Emit smoke for broken machines
            if new_state == MachineState.WAITING_FOR_REPAIR and random.random() < 0.1:
                self.particles.emit_smoke(visual.x + visual.width/2, visual.y + 20)

            # Check for part completion
            if machine.parts_made > visual.parts_made:
                self.particles.emit_complete(visual.x + visual.width/2, visual.y + visual.height/2)

            visual.state = new_state
            visual.parts_made = machine.parts_made
            visual.breakdowns = machine.breakdowns
            self.last_machine_states[i] = new_state

    def _update_repairman_visual(self, dt: float):
        """Update repairman position and state"""
        if self.simulation.repairman_doing_other_job:
            # Go to "other jobs" area
            self.repairman.target_x = 900
            self.repairman.target_y = 520
            self.repairman.doing_other_job = True
            self.repairman.target_machine = None
        elif self.simulation.repairman_target is not None:
            # Go to target machine
            target = self.machine_visuals[self.simulation.repairman_target]
            self.repairman.target_x = target.x + target.width / 2
            self.repairman.target_y = target.y + target.height + 30
            self.repairman.doing_other_job = False
            self.repairman.target_machine = self.simulation.repairman_target

        # Smooth movement
        dx = self.repairman.target_x - self.repairman.x
        dy = self.repairman.target_y - self.repairman.y
        dist = math.sqrt(dx*dx + dy*dy)
        speed = 300  # pixels per second

        if dist > 5:
            self.repairman.x += dx / dist * min(speed * dt, dist)
            self.repairman.y += dy / dist * min(speed * dt, dist)
            self.repairman.animation_frame += dt * 10

        # Update stats
        sim_dt = dt * self.speed / SIM_MINUTE_TO_SECONDS
        if self.simulation.repairman_doing_other_job:
            self.repairman.time_other_jobs += sim_dt
        else:
            self.repairman.time_repairing += sim_dt

    def _draw_machine(self, visual: MachineVisual):
        """Draw a single machine"""
        x, y = int(visual.x), int(visual.y)
        w, h = int(visual.width), int(visual.height)

        # Determine colors based on state
        if visual.state == MachineState.WORKING:
            body_color = COLORS['machine_working']
            border_color = COLORS['success']
        elif visual.state == MachineState.BEING_REPAIRED:
            body_color = COLORS['machine_repair']
            border_color = COLORS['warning']
        elif visual.state == MachineState.WAITING_FOR_REPAIR:
            # Flashing effect
            flash = abs(math.sin(visual.flash_timer)) * 0.5 + 0.5
            body_color = tuple(int(c * flash) for c in COLORS['machine_broken'])
            border_color = COLORS['danger']
        else:
            body_color = COLORS['machine_idle']
            border_color = COLORS['text_dim']

        # Draw machine body
        body_rect = pygame.Rect(x, y, w, h - 30)
        pygame.draw.rect(self.screen, body_color, body_rect, border_radius=10)
        pygame.draw.rect(self.screen, border_color, body_rect, 3, border_radius=10)

        # Draw machine details (gears, display)
        gear_x = x + w // 2
        gear_y = y + 35
        gear_radius = 20

        # Rotating gear animation
        rotation = pygame.time.get_ticks() / 200 if visual.state == MachineState.WORKING else 0
        for i in range(6):
            angle = rotation + i * math.pi / 3
            px = gear_x + math.cos(angle) * gear_radius
            py = gear_y + math.sin(angle) * gear_radius
            pygame.draw.circle(self.screen, COLORS['text_dim'], (int(px), int(py)), 5)
        pygame.draw.circle(self.screen, COLORS['panel'], (gear_x, gear_y), 15)
        pygame.draw.circle(self.screen, COLORS['text_dim'], (gear_x, gear_y), 8)

        # Status indicator light
        light_color = border_color
        pygame.draw.circle(self.screen, light_color, (x + w - 20, y + 15), 8)
        pygame.draw.circle(self.screen, COLORS['text'], (x + w - 20, y + 15), 8, 2)

        # Progress bar background
        bar_y = y + h - 55
        bar_rect = pygame.Rect(x + 10, bar_y, w - 20, 15)
        pygame.draw.rect(self.screen, COLORS['progress_bg'], bar_rect, border_radius=4)

        # Progress bar fill
        if visual.state == MachineState.WORKING:
            progress = visual.work_progress
            fill_color = COLORS['success']
        elif visual.state == MachineState.BEING_REPAIRED:
            progress = visual.repair_progress
            fill_color = COLORS['warning']
        else:
            progress = 0
            fill_color = COLORS['danger']

        fill_width = int((w - 24) * progress)
        if fill_width > 0:
            fill_rect = pygame.Rect(x + 12, bar_y + 2, fill_width, 11)
            pygame.draw.rect(self.screen, fill_color, fill_rect, border_radius=3)

        # Machine label
        label = self.font_medium.render(f"M{visual.id}", True, COLORS['text'])
        self.screen.blit(label, (x + 10, y + 5))

        # Parts count
        parts_text = self.font_small.render(f"Parts: {visual.parts_made}", True, COLORS['text'])
        self.screen.blit(parts_text, (x + 10, y + h - 28))

        # Breakdowns count
        bd_text = self.font_tiny.render(f"BD: {visual.breakdowns}", True, COLORS['text_dim'])
        self.screen.blit(bd_text, (x + w - 45, y + h - 28))

        # Hover effect
        if visual.hovered:
            hover_rect = pygame.Rect(x - 3, y - 3, w + 6, h - 24)
            pygame.draw.rect(self.screen, COLORS['accent'], hover_rect, 3, border_radius=12)

    def _draw_repairman(self):
        """Draw the repairman"""
        x, y = int(self.repairman.x), int(self.repairman.y)

        # Body
        body_color = COLORS['repairman']

        # Walking animation
        bob = math.sin(self.repairman.animation_frame) * 3 if abs(self.repairman.x - self.repairman.target_x) > 5 else 0

        # Head
        pygame.draw.circle(self.screen, COLORS['text'], (x, int(y - 35 + bob)), 15)

        # Body
        pygame.draw.rect(self.screen, body_color, (x - 12, int(y - 20 + bob), 24, 30), border_radius=5)

        # Tool (wrench)
        if not self.repairman.doing_other_job:
            pygame.draw.rect(self.screen, COLORS['text_dim'], (x + 12, int(y - 15 + bob), 20, 6))
            pygame.draw.circle(self.screen, COLORS['text_dim'], (x + 30, int(y - 12 + bob)), 6)

        # Label
        label = "Repairing" if not self.repairman.doing_other_job else "Other Job"
        text = self.font_tiny.render(label, True, COLORS['accent'])
        self.screen.blit(text, (x - text.get_width() // 2, int(y + 15)))

    def _draw_stats_panel(self):
        """Draw statistics panel"""
        panel_x = 1020
        panel_y = 280
        panel_w = 350
        panel_h = 580

        # Panel background
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(self.screen, COLORS['panel'], panel_rect, border_radius=15)
        pygame.draw.rect(self.screen, COLORS['accent'], panel_rect, 2, border_radius=15)

        # Title
        title = self.font_large.render("Statistics", True, COLORS['text'])
        self.screen.blit(title, (panel_x + 20, panel_y + 15))

        # Simulation time
        sim_time = self.simulation.sim_time
        hours = int(sim_time // 60)
        minutes = int(sim_time % 60)
        days = hours // 24
        hours = hours % 24
        time_str = f"Day {days}, {hours:02d}:{minutes:02d}"

        time_label = self.font_medium.render("Simulation Time:", True, COLORS['text_dim'])
        time_value = self.font_medium.render(time_str, True, COLORS['accent'])
        self.screen.blit(time_label, (panel_x + 20, panel_y + 55))
        self.screen.blit(time_value, (panel_x + 20, panel_y + 75))

        # Total parts made
        total_parts = sum(m.parts_made for m in self.simulation.machines)
        parts_label = self.font_medium.render("Total Parts Made:", True, COLORS['text_dim'])
        parts_value = self.font_large.render(str(total_parts), True, COLORS['success'])
        self.screen.blit(parts_label, (panel_x + 20, panel_y + 110))
        self.screen.blit(parts_value, (panel_x + 20, panel_y + 130))

        # Total breakdowns
        total_breakdowns = sum(m.breakdowns for m in self.simulation.machines)
        bd_label = self.font_medium.render("Total Breakdowns:", True, COLORS['text_dim'])
        bd_value = self.font_large.render(str(total_breakdowns), True, COLORS['danger'])
        self.screen.blit(bd_label, (panel_x + 180, panel_y + 110))
        self.screen.blit(bd_value, (panel_x + 180, panel_y + 130))

        # Repairman utilization
        total_time = self.repairman.time_repairing + self.repairman.time_other_jobs
        if total_time > 0:
            utilization = self.repairman.time_repairing / total_time * 100
        else:
            utilization = 0

        util_label = self.font_medium.render("Repairman Utilization:", True, COLORS['text_dim'])
        self.screen.blit(util_label, (panel_x + 20, panel_y + 175))

        # Utilization bar
        bar_rect = pygame.Rect(panel_x + 20, panel_y + 200, panel_w - 40, 20)
        pygame.draw.rect(self.screen, COLORS['progress_bg'], bar_rect, border_radius=5)
        fill_w = int((panel_w - 44) * utilization / 100)
        if fill_w > 0:
            fill_rect = pygame.Rect(panel_x + 22, panel_y + 202, fill_w, 16)
            color = COLORS['success'] if utilization < 70 else (COLORS['warning'] if utilization < 90 else COLORS['danger'])
            pygame.draw.rect(self.screen, color, fill_rect, border_radius=4)

        util_text = self.font_small.render(f"{utilization:.1f}%", True, COLORS['text'])
        self.screen.blit(util_text, (panel_x + panel_w // 2 - 20, panel_y + 202))

        # Parts per machine bar chart
        chart_label = self.font_medium.render("Parts per Machine:", True, COLORS['text_dim'])
        self.screen.blit(chart_label, (panel_x + 20, panel_y + 240))

        max_parts = max((m.parts_made for m in self.simulation.machines), default=1) or 1
        chart_y = panel_y + 270
        bar_height = 22
        bar_spacing = 26

        for i, machine in enumerate(self.simulation.machines):
            # Bar background
            bar_bg = pygame.Rect(panel_x + 50, chart_y + i * bar_spacing, panel_w - 100, bar_height)
            pygame.draw.rect(self.screen, COLORS['progress_bg'], bar_bg, border_radius=4)

            # Bar fill
            fill_w = int((panel_w - 104) * machine.parts_made / max_parts) if max_parts > 0 else 0
            if fill_w > 0:
                fill_rect = pygame.Rect(panel_x + 52, chart_y + i * bar_spacing + 2, fill_w, bar_height - 4)
                # Color based on breakdown rate
                if self.machine_visuals[i].breakdowns == 0:
                    color = COLORS['success']
                elif self.machine_visuals[i].breakdowns < 3:
                    color = COLORS['warning']
                else:
                    color = COLORS['danger']
                pygame.draw.rect(self.screen, color, fill_rect, border_radius=3)

            # Machine label
            m_label = self.font_tiny.render(f"M{i}", True, COLORS['text_dim'])
            self.screen.blit(m_label, (panel_x + 22, chart_y + i * bar_spacing + 4))

            # Parts count
            count_text = self.font_tiny.render(str(machine.parts_made), True, COLORS['text'])
            self.screen.blit(count_text, (panel_x + panel_w - 45, chart_y + i * bar_spacing + 4))

        # Instructions
        inst_y = panel_y + panel_h - 70
        inst_text = [
            "Click machine to cause breakdown",
            "SPACE: Pause | R: Reset | Q: Quit"
        ]
        for i, text in enumerate(inst_text):
            inst_surf = self.font_tiny.render(text, True, COLORS['text_dim'])
            self.screen.blit(inst_surf, (panel_x + 20, inst_y + i * 18))

    def _draw_repairman_area(self):
        """Draw the 'other jobs' area for the repairman"""
        x, y = 820, 480
        w, h = 180, 100

        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, COLORS['panel'], rect, border_radius=10)
        pygame.draw.rect(self.screen, COLORS['text_dim'], rect, 2, border_radius=10)

        label = self.font_medium.render("Other Jobs", True, COLORS['text_dim'])
        self.screen.blit(label, (x + w // 2 - label.get_width() // 2, y + 10))

        # Show if repairman is doing other jobs
        if self.repairman.doing_other_job:
            status = self.font_small.render("In Progress...", True, COLORS['accent'])
            self.screen.blit(status, (x + w // 2 - status.get_width() // 2, y + 40))

    def _check_machine_click(self, pos):
        """Check if a machine was clicked"""
        for i, visual in enumerate(self.machine_visuals):
            rect = pygame.Rect(visual.x, visual.y, visual.width, visual.height - 30)
            if rect.collidepoint(pos):
                if visual.state == MachineState.WORKING:
                    self.simulation.machines[i].force_break()
                    return True
        return False

    def _check_machine_hover(self, pos):
        """Check machine hover state"""
        for visual in self.machine_visuals:
            rect = pygame.Rect(visual.x, visual.y, visual.width, visual.height - 30)
            visual.hovered = rect.collidepoint(pos)

    def run(self):
        """Main game loop"""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_q, pygame.K_ESCAPE):
                        self.running = False
                    elif event.key == pygame.K_SPACE:
                        self.simulation.paused = not self.simulation.paused
                        self.pause_button.text = "RESUME" if self.simulation.paused else "PAUSE"
                    elif event.key == pygame.K_r:
                        self._reset()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if self.pause_button.handle_event(event):
                            self.simulation.paused = not self.simulation.paused
                            self.pause_button.text = "RESUME" if self.simulation.paused else "PAUSE"
                        elif self.reset_button.handle_event(event):
                            self._reset()
                        else:
                            self._check_machine_click(event.pos)

                self.speed_slider.handle_event(event)
                self.pause_button.handle_event(event)
                self.reset_button.handle_event(event)

            # Update hover states
            mouse_pos = pygame.mouse.get_pos()
            self._check_machine_hover(mouse_pos)

            # Update speed from slider
            self.speed = self.speed_slider.value

            # Step simulation
            if not self.simulation.paused:
                sim_step = dt * self.speed / SIM_MINUTE_TO_SECONDS
                self.simulation.step(sim_step)

            # Update visuals
            self._update_machine_visuals(dt)
            self._update_repairman_visual(dt)
            self.particles.update(dt)

            # Draw
            self.screen.fill(COLORS['background'])

            # Title
            title = self.font_large.render("Machine Shop Simulation", True, COLORS['text'])
            self.screen.blit(title, (80, 30))

            subtitle = self.font_small.render("Based on SimPy Machine Shop Example", True, COLORS['text_dim'])
            self.screen.blit(subtitle, (80, 65))

            # Draw machines
            for visual in self.machine_visuals:
                self._draw_machine(visual)

            # Draw repairman area
            self._draw_repairman_area()

            # Draw repairman
            self._draw_repairman()

            # Draw particles
            self.particles.draw(self.screen)

            # Draw UI
            self.speed_slider.draw(self.screen)
            self.pause_button.draw(self.screen)
            self.reset_button.draw(self.screen)

            # Draw stats panel
            self._draw_stats_panel()

            # Paused indicator
            if self.simulation.paused:
                pause_text = self.font_large.render("PAUSED", True, COLORS['warning'])
                self.screen.blit(pause_text, (WINDOW_WIDTH // 2 - 60, 30))

            pygame.display.flip()

        pygame.quit()

    def _reset(self):
        """Reset the simulation"""
        self.simulation.reset()
        self.particles = ParticleSystem()
        self.machine_visuals = self._create_machine_layout()
        self.repairman = RepairmanVisual(x=900, y=700, target_x=900, target_y=700)
        self.last_machine_states = {}
        self.pause_button.text = "PAUSE"


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    print("=" * 60)
    print("Machine Shop Simulation - Interactive Animation")
    print("=" * 60)
    print("\nControls:")
    print("  - Click on working machine: Cause breakdown")
    print("  - Speed slider: Adjust simulation speed (0.5x - 20x)")
    print("  - SPACE / Pause button: Pause/Resume simulation")
    print("  - R / Reset button: Reset simulation")
    print("  - Q / ESC: Quit")
    print("\nStarting animation...")
    print("=" * 60)

    animation = MachineShopAnimation()
    animation.run()


if __name__ == "__main__":
    main()
