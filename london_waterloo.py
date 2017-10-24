#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 26 20:55:49 2017

@author: Harry
"""

# import simpy for discrete-event simulation
import simpy
# import random for sampling random numbers
from numpy import random
# import numpy for maths and other useful things
import numpy as np
# import pandas for data analysis
import pandas as pd

# create an empty dictionary to populate with data
output = {'Train':[], 'Departure Time':[]}

# create a list of the platforms
free_platforms = list(range(1,25))

# define the triangular distribution
def triangular_distribution(minimum, maximum, median):
    x = random.triangular(minimum, median, maximum)
    return x 

# define the uniform distribution
def uniform_distribution(minimum, maximum):
    x = random.uniform(minimum, maximum)
    return x

# define the source
def source(env):
    i = 1
    while True:
        # start the process
        yield env.timeout(10)
        env.process(run_in_run_out_waterloo(env, waterloo_platforms, i))
        i += 1
        
# describe the process
def run_in_run_out_waterloo(env, waterloo_platforms, name):
    # global is used so that this function can modify the platform list
    global free_platforms
    
    # request resource
    platform_request = waterloo_platforms.request()
    yield platform_request
    
    # pick one of the free platforms
    platform_choice = random.choice(free_platforms)
    free_platforms.remove(platform_choice)
    
    # request run in authority
    print("%ds: Train %d requesting run into platform %d" % (env.now, name, platform_choice))
    run_in_request = run_in_authority.request()
    yield run_in_request
    
    # run in
    print("%ds: Train %d running into platform %d" % (env.now, name, platform_choice))
    yield env.timeout(uniform_distribution(94,100))
    print("%ds: Train %d arrived at platform %d and boarding" % (env.now, name, platform_choice))
    
    # release run in authority
    run_in_authority.release(run_in_request)
    
    # board passengers
    yield env.timeout(triangular_distribution(180, 600, 300))
    print("%ds: Train %d fully-boarded and requesting to depart platform %d" % (env.now, name, platform_choice))
    
    # request run out authority
    run_out_request = run_out_authority.request()
    yield run_out_request
    
    # run out
    output['Departure Time'].append(env.now)
    output['Train'].append(name)
    print("%ds: Train %d running out of platform %d" % (env.now, name, platform_choice))
    yield env.timeout(uniform_distribution(119,125))
    print("%ds: Train %d has left and platform %d is now free" % (env.now, name, platform_choice))
    
    # release resource
    waterloo_platforms.release(platform_request)
    
    # add platform back into list of free platforms
    free_platforms.append(platform_choice)
   
    # release run out authority
    run_out_authority.release(run_out_request)
    
        
# create the simpy environment
env = simpy.Environment()

# define the resources
waterloo_platforms = simpy.Resource(env, capacity=24)
run_in_authority = simpy.Resource(env, capacity=3)
run_out_authority = simpy.Resource(env, capacity=3)

# start the source process
env.process(source(env))

# run the process
env.run(until = 10800)

# convert the dictionary to a csv
df = pd.DataFrame.from_dict(output, orient = 'columns')

# write the data to a csv file
df.to_csv('output.csv', index = False)
