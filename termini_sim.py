# Termini simulation
# Helps answer the question: how many trains per hour can my termini design support
# User inputs range of termini
# User inputs range of dwell times
# Program automatically tests all combinations
# v0.1 10/04/2016

# Modules
import simpy
import random
from matplotlib import pyplot as plt
import pandas as pd
import seaborn as sns

 
############ The Simulation Setup ############
 
# Time for each simulation
SIM_TIME = 86400 # 86400s = 1 day
 
# Run-in variables
run_in_min, run_in_med, run_in_max = 100.0, 200.0, 300.0 # Distances (m)
run_in_s = 20.0 # Speed (m/s)
num_termini = 1.0
 
# Dwell variables (s)
dwell_med = 300.0
dwell_min = dwell_med * 0.5
dwell_max = dwell_med * 1.5
 
# Input headways: throw trains at the simulator
input_headway = 30
 
# Triangular distribution: use for run in distance and dwell times
def triangular(x, y, z):
            t = random.triangular(x, y, z)
            return t
 
# Run-in and run-out time function
def run_in(x, y, z):
            platform_distance = triangular(x, y, z)
            return platform_distance / run_in_s
 
# Empty dictionarys to use for analysis
d = {"N_Termini":"", "T_Dwell":"", "TPH_Achieved":""}
l_termini = []
l_dwell = []
l_tph = []
 
############ The Main Simulation Flow ############
# Train generation function (the source)
def source(env):
            while True:
                        c = termini(env, termini_resource)
                        env.process(c)
                        yield env.timeout(input_headway) # time before next train is generated
 
# Arrive and leave function
def termini(env, res):
 
            # Set up resource to be used
           
            req = res.request()
           
            # Request platform and wait if not available
            yield req
           
            # Run into platform
            run_in_time = run_in(run_in_min, run_in_med, run_in_max)
            yield env.timeout(run_in_time)
           
            # Dwell at termini
            yield env.timeout(triangular(dwell_min, dwell_med, dwell_max))
 
            # depart platform
            yield env.timeout(run_in_time)
 
            # Release platform
            res.release(req)
 
            l.append(env.now)
 
 
############ Setting Up and Running the Simulation ############
 
# Create simpy environment
 
 
# Resources
 
 
# Start the simulation
#env.process(source(env))
#env.run(until = SIM_TIME)
 
# For loop to start number of termini simulations
for t in range(1, 10): # number of termini
            for n in range(120, 601, 60): # dwell median
                        l = []
                        dwell_med = n
                        env = simpy.Environment(initial_time = 0)
                        termini_resource = simpy.Resource(env, capacity = t)
                        env.process(source(env))
                        env.run(until = SIM_TIME)
                        
                        l_termini.append(t)
                        l_dwell.append(n)
                        l_tph.append(len(l)/(SIM_TIME/3600))
                        
d["N_Termini"] = l_termini
d["T_Dwell"] = l_dwell
d["TPH_Achieved"] = l_tph

df = pd.DataFrame(d)

#plt.figure()
df.plot.scatter(x = 'N_Termini', y = 'T_Dwell', c = 'TPH_Achieved', s = 100)
plt.show()

print df
                        
