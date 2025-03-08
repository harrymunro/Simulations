import random
import simpy
import osmnx as ox
from osmnx import truncate
import networkx as nx
from matplotlib import pyplot as plt
from celluloid import Camera

# --- 1) SET UP THE MAP WITH OSMnx ---

# Latitude and Longitude for a point in Holborn, London
latitude = 51.5175
longitude = -0.117

# Create a graph from a point (driveable roads, 500m bounding box)
G = ox.graph_from_point((latitude, longitude), dist=500, dist_type='bbox', network_type='drive')

# Keep the largest strongly connected component
G = truncate.largest_component(G, strongly=True)

# Pick two random nodes for origin/destination
origin, destination = random.sample(list(G.nodes), 2)

# Compute the shortest path
shortest_path = nx.shortest_path(G, origin, destination, weight='length')

# Pre‑compute edge lengths for convenience
# (OSMnx already stores distances but let's explicitly ensure we have them)
lengths = {}
for u, v, data in G.edges(data=True):
    # The distance field is usually 'length' in OSMnx
    lengths[(u, v)] = data.get('length', 0)
    # For undirected graphs, also set the reverse
    if not G.is_directed():
        lengths[(v, u)] = lengths[(u, v)]

# --- 2) SET UP A SIMPY ENV AND OUR PROCESS (TRUCK) ---

# We'll store the truck positions over time in this list:
truck_positions = []


def drive_truck(env, path, speed_km_per_h, G, lengths, positions):
    """
    A generator function for the truck, which travels along the given path (list of nodes).
    After each edge, it yields a SimPy timeout for the correct travel time,
    and stores the node/time in 'positions' for later.
    """
    # Convert speed from km/h to m/s:
    speed_m_s = speed_km_per_h * 1000.0 / 3600.0

    # Start at the first node in the path
    current_node = path[0]
    start_time = env.now
    positions.append((env.now, current_node))  # Record initial position

    # Iterate through consecutive edges in the path
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]
        distance_m = lengths.get((u, v), 0.0)
        travel_time_s = distance_m / speed_m_s

        # SimPy: wait for travel_time_s
        yield env.timeout(travel_time_s)

        # After waiting, we've reached node v
        current_node = v
        positions.append((env.now, current_node))

    # Optionally do something at destination
    # e.g. print that the truck has arrived
    print(f"Truck arrived at {path[-1]} after {env.now - start_time:.1f} seconds.")


# Create environment
env = simpy.Environment()

# Create and start the truck process
speed_km_per_h = 30.0  # example: 30 km/h
env.process(drive_truck(env, shortest_path, speed_km_per_h, G, lengths, truck_positions))

# Run until done
env.run()

# --- 3) ANIMATE THE JOURNEY USING THE RECORDED POSITIONS ---

# truck_positions is now a list of (time_s, node_id).
# We can do a simple frame‑by‑frame approach with celluloid Camera.

fig, ax = plt.subplots()
camera = Camera(fig)

# We'll step through each recorded node transition in time order
# and highlight the route up to that point.
for i in range(len(truck_positions)):
    # Current node in the sequence:
    _, current_node = truck_positions[i]

    # Plot the underlying graph
    # (For clarity, we use show=False, close=False to keep re-plotting each frame)
    ox.plot_graph(
        G,
        ax=ax,
        show=False,
        close=False,
        node_size=0,
        bgcolor='k'
    )

    # Plot the path up to current index
    partial_route = [x[1] for x in truck_positions[:i + 1]]  # the visited node IDs
    ox.plot_graph_route(
        G,
        partial_route,
        route_linewidth=6,
        node_size=0,
        bgcolor='k',
        route_color='r',
        orig_dest_node_size=100,
        ax=ax,
        show=False,
        close=False
    )
    camera.snap()

animation = camera.animate()
animation.save('truck_journey.gif', writer='imagemagick')
print("Saved animation to truck_journey.gif")
