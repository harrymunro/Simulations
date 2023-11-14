# version 3: created live plots and animated trains
# version 4: need to: 
# - DONE output all raw data into pandas dataframe
# version 5:
# - DONE change logic so that platform 2 outbound route clears AFTER crossing point 30B
# - DONE add train number to box
# - DONE add simulation counter to window as its own function with custom timestep in bottom right space
# - add real time clock to simulation and a speed indicator (e.g. 10x real-time speed)

"""
Termini example.

Scenario:
  A termini has a three platforms and defines
  a dwell processes that takes some (random) time.

  Trains arrive at the termini at a random time. If one platform
  is available, it starts the process of run in, dwell and run-out.

  If not then the train waits until a platform is free.

  Conflicts and movement authoritites have been captured.

"""

### Setup animation ### 
show_animation = True
hide_plots = False

# importing libraries to use (libraries contain code shortcuts)
import random
import simpy # DES
import numpy as np # a maths and plotting module
import pandas as pd # more data analysis
import matplotlib.pyplot as plt # 
import seaborn as sns
import math
import time
import sys
if sys.version_info[0] == 3:
    # brew install python-tk
    from tkinter import *
else:
    from Tkinter import *

# Analyse the overall headway
def headway_analysis(time):
	time2 = time[1:]
	time3 = time[:-1]
	headway = []
	for i in range(len(time2)):
		headway.append(time2[i] - time3[i])
	return headway

################ SET UP ANIMATION CANVAS #################
class Train:
    def __init__(self, canvas, x1, y1, x2, y2, tag):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.canvas = canvas
        self.train = canvas.create_rectangle(self.x1, self.y1, self.x2, self.y2, fill="red", tags = tag)
        self.train_number = canvas.create_text(((self.x2 - self.x1)/2 + self.x1), ((self.y2 - self.y1)/2 + self.y1), text = tag)
        self.canvas.update()

    def move_train(self, deltax, deltay):
        self.canvas.move(self.train, deltax, deltay)
        self.canvas.move(self.train_number, deltax, deltay)
        self.canvas.update()
        
    def remove_train(self):
        self.canvas.delete(self.train)
        self.canvas.delete(self.train_number)
        self.canvas.update()

class Clock:
    def __init__(self, canvas, x1, y1, x2, y2, tag):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.canvas = canvas
        self.train = canvas.create_rectangle(self.x1, self.y1, self.x2, self.y2, fill="#fff")
        self.time = canvas.create_text(((self.x2 - self.x1)/2 + self.x1), ((self.y2 - self.y1)/2 + self.y1), text = "Time = "+str(tag)+"s")
        self.canvas.update()

    def tick(self, tag):
        self.canvas.delete(self.time)
        self.time = canvas.create_text(((self.x2 - self.x1)/2 + self.x1), ((self.y2 - self.y1)/2 + self.y1), text = "Time = "+str(tag)+"s")
        self.canvas.update()
    

if show_animation == True:
    animation = Tk()
    #bitmap = BitmapImage(file="uxbridge.bmp")

    #im = PhotoImage(file="uxbridge_resized.gif")

    canvas = Canvas(animation, width = 800, height = 400)
    #canvas.create_image(0,0, anchor=NW, image=im)
    animation.title("Uxbridge Termini Simulation")

    canvas.pack()

#### matplotlib plots
    

if show_animation == True and hide_plots == False:
    f = plt.Figure(figsize=(5,4), dpi=100)

    a1 = f.add_subplot(221) # mean headway
    a2 = f.add_subplot(222) # TPH meter
    a3 = f.add_subplot(223) # headway distribution
    a4 = f.add_subplot(224) # train count

    a1.plot()
    a2.plot()
    a3.plot()
    a4.plot()

    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg#, NavigationToolbar2TkAgg
    
    dataPlot = FigureCanvasTkAgg(f, master=animation)
    dataPlot.draw()
    dataPlot.get_tk_widget().pack(side=TOP, fill=BOTH, expand=1)
    f.tight_layout()

    canvas.pack()

# platforms
if show_animation == True:
    canvas.create_rectangle(50, 100, 200, 150, fill = "yellow")
    canvas.create_rectangle(50, 200, 200, 250, fill = "yellow")

    canvas.create_line(50, 75, 200, 75, fill="green", width=3) # platform 4
    canvas.create_line(50, 175, 200, 175, fill="green", width=3) # platform 2/3
    canvas.create_line(50, 275, 200, 275, fill="green", width=3) # platform 1

    canvas.create_text(125, 110, text = "Platform 4")
    canvas.create_text(125, 140, text = "Platform 3")
    canvas.create_text(125, 210, text = "Platform 2")
    canvas.create_text(125, 240, text = "Platform 1")

# track
    canvas.create_line(200, 75, 650, 75, fill="green", width=3) # platform 4 run out
    canvas.create_line(200, 175, 650, 175, fill="green", width=3) # platform 2/3 run in
    canvas.create_line(300, 175, 400, 75, fill="green", width=3)
    canvas.create_line(450, 75, 600, 175, fill="green", width=3)
    canvas.create_line(450, 175, 600, 75, fill="green", width=3)
    canvas.create_line(200, 275, 300, 275, fill="green", width=3)
    canvas.create_line(300, 275, 400, 175, fill="green", width=3)

############ END OF CANVAS #################

# set platform status - changing one of these to "True" at this stage will permanently close the platform as no train will actually be present in the platform, so the platform will never become free
platform_1_occupied = False
platform_2_occupied = False
platform_4_occupied = False
NUM_PLATFORMS = 3  # Number of platforms in the termini (needs to match how many platforms are initially set to "False" occupancy

# setting up empty lists to store results in
time = []
headway = []
moving_avg_headway = []
moving_stdev_headway = []
train_number = []
n = 0

# set up general parameters
RANDOM_SEED = 45
T_INTER = 60     # Arrival headway: create a train on average every T_INTER seconds, setting this to "1" is a reasonable approximation to "as fast as possible" without slowing down the simulation
SIM_TIME = 100000     # Simulation time in seconds
dwelltime = 60

# set up random variable for train arrival times
def arrival_interval(T_INTER):
    t = random.expovariate(1.0/T_INTER) # exponential distribution, not particularly useful for "as fast as possible", more useful if we want to try to reproduce real world arrival times
    return t

# set up the dwell variable
def dwell():
	# a few different options here - lognormal is normally most representative of human error and general dwell times
	#t = random.randint(120, 240) # uniformly distributed
    t = random.lognormvariate(math.log(dwelltime), 1) # lognormally distributed
        #t = random.triangular(dwelltime * 0.9, dwelltime * 1.1, dwelltime) # triangular distribution (low, high, mid)
        #t = dwelltime # fixed dwell
    return t

# define empty dictionary
output_dict = {'Train ID':[], 'Time':[], 'Event Type': [], 'Event Description': []}
ID = []
t_now = []
e_type = []
e_description = []


        

# define the termini
class Termini(object):
    """A termini has a limited number of platforms (``NUM_platforms``) to
    clean trains in parallel.

    Trains have to request one of the platforms. When they got one, they
    can start the washing processes and wait for it to finish (which
    takes ``dwelltime`` minutes).
    """
    def __init__(self, env, num_platforms):
        self.env = env
	# below are the "resources" the termini has which trains compete for
        self.platform = simpy.Resource(env, num_platforms)
        self.run_out_authority = simpy.Resource(env, 1)
        self.run_in_authority = simpy.Resource(env, 1)
        self.p1_outbound = simpy.Resource(env, 1)
        self.p2_outbound = simpy.Resource(env, 1)

    def dwell(self, train, platform):
        """The dwell processes."""
        yield self.env.timeout(dwell()) # this calls the dwell time

def write_data(train_id, time, event, description):
    output_dict['Train ID'].append(train_id)
    output_dict['Time'].append(time)
    if event == 'req':
        output_dict['Event Type'].append('Request resource')
    elif event == 'sei':
        output_dict['Event Type'].append('Seize resource')
    elif event == 'rel':
        output_dict['Event Type'].append('Release resource')
    elif event == 'sp':
        output_dict['Event Type'].append('Start process')
    elif event == 'fp':
        output_dict['Event Type'].append('Finish process')
    else:
        raise Exception('Event type code not properly defined in data write')
    output_dict['Event Description'].append(description)
    

# below is the process which a train follows when generated
def train(env, name, tr):
    """The train process (each train has a ``name``) arrives at the termini
    (``tr``) and requests a cleaning machine.

    It then starts the washing process, waits for it to finish and
    leaves to never come back ...

    """
# setting global variables - this allows the processes to tell eachother when a specific platform is free/emptys
    global platform_1_occupied
    global platform_2_occupied
    global platform_4_occupied
    global headway
    global a
    global f
    global dataplot
    global n
    train_id = name
    
    
    with tr.platform.request() as request: 
        canvas.update()

        write_data(name, env.now, 'req', 'Request a platform at Uxbridge')

        yield request # train asks is there spare capacity at kings cross, if not then it waits here

        write_data(name, env.now, 'sei', 'Seize a platform at Uxbridge')


        
        if platform_1_occupied == False: # checks whether this spare capacity is at platform 1, if not then skips forward to platform 2 about 20 lines below
            platform_1_occupied = True # sets status of platform 1 as being occupied
            with tr.run_in_authority.request() as request: # this line of code sets up the resource to be requested
                write_data(name, env.now, 'req', 'Request general run_in authority')
                yield request # requests the resource "run_in_authority"
                train = Train(canvas, 600,165,700,185, name)
                write_data(name, env.now, 'sei', 'Seize general run_in authority')
                write_data(name, env.now, 'sp', 'Start run-in to platfom 1')
                yield env.timeout(13.3) # start run in to platform 1
                train.move_train(-100, 0)
                run_time = 66.8
                yield env.timeout(run_time/4) # complete run-in to platform 1
                train.move_train(-150, 0)
                yield env.timeout(run_time/4) # complete run-in to platform 1
                train.move_train(-75, 50)
                yield env.timeout(run_time/4) # complete run-in to platform 1
                train.move_train(-75, 50)
                yield env.timeout(run_time/4) # complete run-in to platform 1
                train.move_train(-100, 0)
                write_data(name, env.now, 'fp', 'Finish run-in to platfom 1')
                tr.run_in_authority.release(request) # releases the resource "run_in_authority"
                write_data(name, env.now, 'rel', 'Release general run-in authority')
            door_open = env.now
            write_data(name, env.now, 'sp', 'Start dwell at platform 1')
            yield env.process(tr.dwell(name, "platform 1"))
            write_data(name, env.now, 'fp', 'Finish dwell at platform 1')
            with tr.run_out_authority.request() as request:
                write_data(name, env.now, 'req', 'Request general run-out authority')
                yield request
                write_data(name, env.now, 'sei', 'Seize general run-out authority')
                #train.remove_train()
                with tr.p2_outbound.request() as request:
                    write_data(name, env.now, 'req', 'Request platform 2 outbound route')
                    yield request
                    write_data(name, env.now, 'sei', 'Seize platform 2 outbound route')
                    with tr.p1_outbound.request() as request:
                        write_data(name, env.now, 'req', 'Request platform 1 outbound route')
                        yield request
                        write_data(name, env.now, 'sei', 'Seize platform 1 outbound route')
                        write_data(name, env.now, 'sp', 'Start run out from platform 1')
                        train.move_train(100, 0)
                        # split up the run out
                        run_time = 78.9
                        yield env.timeout(78.9/4) # run out of platform 1 part 1
                        train.move_train(100, -50)
                        yield env.timeout(78.9/4) # run out of platform 1 part 2
                        train.move_train(100, -50)
                        yield env.timeout(78.9/4) # run out of platform 1 part 3
                        train.move_train(75, -50)
                        yield env.timeout(78.9/4) # run out of platform 1 part 4
                        train.move_train(75, -50)
                        write_data(name, env.now, 'fp', 'Finish run out from platform 1')
                        tr.p1_outbound.release(request) # trains can run in now#
                        write_data(name, env.now, 'rel', 'Release platform 1 outbound route')
               
                    write_data(name, env.now, 'sp', 'Start clearing point 30B')
                    run_time = 13.9/2
                    yield env.timeout(13.9/2) # clear availability - next train can depart
                    train.move_train(100, 0)
                    yield env.timeout(13.9/2) # clear availability - next train can depart
                    write_data(name, env.now, 'fp', 'Finish clearing point 30B')
                    tr.p2_outbound.release(request)
                    write_data(name, env.now, 'rel', 'Release platform 2 outbound route')
                tr.run_out_authority.release(request)
                write_data(name, env.now, 'rel', 'Release general run-out authority')
                platform_1_occupied = False
                train.remove_train()

        elif platform_2_occupied == False: # train skips forward to here if platform 1 is in use
            platform_2_occupied = True # sets status of platform 2 as being occupied
            with tr.run_in_authority.request() as request:
                write_data(name, env.now, 'req', 'Request general run-in authority')
                yield request
                write_data(name, env.now, 'sei', 'Seize general run-in authority')
                with tr.p1_outbound.request() as request:
                    write_data(name, env.now, 'req', 'Request platform 1 outbound resource')
                    yield request
                    train = Train(canvas, 600,165,700,185, name)
                    write_data(name, env.now, 'sei', 'Seize platform 1 outbound resource')
                    write_data(name, env.now, 'sp', 'Start platform 2 run-in')
                    yield env.timeout(12.7)
                    train.move_train(-100, 0)
                    run_time = 66.7
                    yield env.timeout(run_time/3) # time to clear platform 1 outbound
                    train.move_train(-100, 0)
                    yield env.timeout(run_time/3) # time to clear platform 1 outbound
                    train.move_train(-100, 0)
                    yield env.timeout(run_time/3) # time to clear platform 1 outbound
                    train.move_train(-100, 0)
                    write_data(name, env.now, 'rel', 'Release platform 1 outbound resource')
                    tr.p1_outbound.release(request) # trains can run into platform 1 now
                    
                yield env.timeout(8.1) # complete run-in to platform 2
                write_data(name, env.now, 'fp', 'Finish run-in to platform 2')
                train.move_train(-100, 0)
                tr.run_in_authority.release(request)
                write_data(name, env.now, 'rel', 'Release run-in authority')
            door_open = env.now
            write_data(name, env.now, 'sp', 'Start dwell at platform 2')
            yield env.process(tr.dwell(name, "platform 2"))
            write_data(name, env.now, 'fp', 'Finish dwell at platform 2')
            with tr.run_out_authority.request() as request:
                write_data(name, env.now, 'req', 'Request general run-out authority')
                yield request
                write_data(name, env.now, 'sei', 'Seize run-out authority')
                with tr.p2_outbound.request() as request:
                    write_data(name, env.now, 'req', 'Request platform 2 outbound route')
                    yield request
                    write_data(name, env.now, 'sei', 'Seize platform 2 outbound route')
                    train.move_train(150, 0)
                    run_time = 41.5
                    write_data(name, env.now, 'sp', 'Start run-out of platform 2')
                    yield env.timeout(run_time/3) # time taken to run out of platform 2
                    train.move_train(50, -50)
                    yield env.timeout(run_time/3) # time taken to run out of platform 2
                    train.move_train(50, -50)
                    yield env.timeout(run_time/3) # time taken to run out of platform 2
                    train.move_train(50, 0)
                    write_data(name, env.now, 'fp', 'Finish run-out of platform 2')
                    
                    run_time = 21.8
                    yield env.timeout(run_time/2) # clear point 30B
                    train.move_train(100, 0)
                    yield env.timeout(run_time/2) # clear point 30B
                    train.move_train(100, 0)
                    write_data(name, env.now, 'sp', 'Start clearing point 30B')

                    yield env.timeout(12.2) # clear availability
                    write_data(name, env.now, 'fp', 'Finish clearing point 30B')
                    tr.p2_outbound.release(request)
                    write_data(name, env.now, 'rel', 'Release platform 2 outbound route')
                tr.run_out_authority.release(request)
                write_data(name, env.now, 'rel', 'Release general run-out authority')
                platform_2_occupied = False
                train.remove_train()

        elif platform_4_occupied == False: # train skips forward to here if platform 2 is in use
            platform_4_occupied = True # sets status of platform 4 as being occupied
            with tr.run_in_authority.request() as request:
                write_data(name, env.now, 'req', 'Request general run-in authority')
                yield request
                write_data(name, env.now, 'sei', 'Seize general run-in authority')
                with tr.p2_outbound.request() as request:
                    write_data(name, env.now, 'req', 'Request platform 2 outbound route')
                    yield request
                    write_data(name, env.now, 'sei', 'Seize platform 2 outbound route')
                    with tr.p1_outbound.request() as request:
                        write_data(name, env.now, 'req', 'Request platform 1 outbound route')
                        yield request
                        train = Train(canvas, 600,165,700,185, name)
                        write_data(name, env.now, 'sei', 'Seize platform 1 outbound route')
                        train.move_train(-50, 0)
                        write_data(name, env.now, 'sp', 'Start run-in to platform 4')
                        yield env.timeout(13.5) # MW58 approach
                        train.move_train(-75, -50)
                        run_time = 46.7
                        yield env.timeout(run_time/2) # time to clear p1 outbound route
                        train.move_train(-75, -50)
                        yield env.timeout(run_time/2) # time to clear p1 outbound route
                        train.move_train(-100, 0)
                        tr.p1_outbound.release(request)  
                        write_data(name, env.now, 'rel', 'Release platform 1 outbound route')
                    yield env.timeout(2.1) # clear p2 outbound route
                    train.move_train(-100, 0)
                    tr.p2_outbound.release(request)
                    write_data(name, env.now, 'rel', 'Release platform 2 outbound route')
                yield env.timeout(15.5) # finish run-in
                write_data(name, env.now, 'fp', 'Finish run-in to platform 4')
                train.move_train(-100, 0)
                tr.run_in_authority.release(request)
                write_data(name, env.now, 'rel', 'Release general run-in authority')
            door_open = env.now
            write_data(name, env.now, 'sp', 'Start dwell at platform 4')
            yield env.process(tr.dwell(name, "platform 4"))
            write_data(name, env.now, 'fp', 'Finish dwell at platform 4')
            with tr.run_out_authority.request() as request:
                write_data(name, env.now, 'req', 'Request general run-out authority')
                yield request
                write_data(name, env.now, 'sei', 'Seize general run-out authority')
                train.move_train(100, 0)
                run_time = 35.2
                write_data(name, env.now, 'sp', 'Start run-out from platform 4')
                yield env.timeout(run_time/3) # run out
                train.move_train(125, 0)
                yield env.timeout(run_time/3) # run out
                train.move_train(125, 0)
                yield env.timeout(run_time/3) # run out
                train.move_train(125, 0)
                write_data(name, env.now, 'fp', 'Finish run-out from platform 4')
                write_data(name, env.now, 'sp', 'Start clearing point 30B')
                yield env.timeout(12.1) # clear run out route
                write_data(name, env.now, 'fp', 'Finish clearing point 30B')
                train.remove_train()
                tr.run_out_authority.release(request)
                write_data(name, env.now, 'rel', 'Release general run-out authority')
                platform_4_occupied = False

        tr.platform.release(request)     
        write_data(name, env.now, 'rel', 'Release platform at Uxbridge')
    
    # setup for moving average headway calculation
    time.append(env.now) # recording the time for headway calculation
    n += 1
    train_number.append(n)

    headway = headway_analysis(time)
    print(np.mean(headway))
    moving_avg_headway.append(np.mean(headway))
    moving_stdev_headway.append(np.std(headway))

    if show_animation == True and hide_plots == False:
        a1.cla()
        a1.set_xlabel("Number of Trains")
        a1.set_ylabel("Mean Headway (s)")
        a1.plot(moving_avg_headway)

        # setup for headway distribution
        a2.cla()
        a2.set_xlabel("Number of Trains")
        a2.set_ylabel("Frequency")
        a2.hist(headway)

        # setup for train count
        a3.cla()
        a3.set_xlabel("Number of Trains")
        a3.set_ylabel("Headway(s)")
        a3.plot(headway)

        # setup for TPH meter
        a4.cla()
        #TPH = 3600.0/np.mean(headway)
        a4.set_xlabel("Number of Trains")
        a4.set_ylabel("StDev Headway(s)")
        a4.plot(moving_stdev_headway)
    
        dataPlot.show()
        canvas.update()

# create the simulated world
def setup(env, num_platforms, t_inter):
    """Create a termini, a number of initial trains and keep creating trains
    approx. every ``t_inter`` seconds."""
    # Create the termini
    termini = Termini(env, num_platforms)
    
    # Create x initial trains
    for i in range(1):
        env.process(train(env, 'Train %d' % i, termini))

    # Create more trains while the simulation is running
    while True:
        yield env.timeout(arrival_interval(t_inter))
        i += 1
        env.process(train(env, 'Train %d' % i, termini))

def create_clock(env):
    clock = Clock(canvas, 500,250,700,300, env.now)
    while True:
        yield env.timeout(1)
        clock.tick(env.now)
        

# Setup and start the simulation
print('Termini Simulation')
random.seed(RANDOM_SEED)  # This helps reproducing the results

# Create an environment and start the setup process
#env = simpy.Environment()

# Real time sim
env = simpy.rt.RealtimeEnvironment(factor = 0.01, strict = False)

# Start the process
env.process(setup(env, NUM_PLATFORMS, T_INTER))
env.process(create_clock(env))

# Execute!
env.run(until=SIM_TIME)

# keep display open
mainloop()


#####################################
### BELOW IS FOR POST PROCESSING OF RESULTS ###
#####################################
df = pd.DataFrame(output_dict)
df.to_csv('uxbridge_sim_output_raw.csv')

headway = headway_analysis(time)

# define print descriptive statistics function
def descriptive_stats(x, name):
    # Python 3 print statements
    if sys.version_info[0] == 3:
        print("\nDescriptive Statistics for %s" % name)
        print("count = %d" % len(x))
        print("mean = %d" % np.mean(x))
        print("std = %d" % np.std(x))
        print("min = %d" % np.min(x))
        print("25%% = %d" % np.percentile(x, 25))
        print("50%% = %d" % np.percentile(x, 50))
        print("75%% = %d" % np.percentile(x, 75))
        print("max = %d" % np.max(x))
        print("mean headway converts to %d TPH" % (3600.0/np.mean(x)))

    # Compatability for Python 2
    else:
        pass

descriptive_stats(headway, "Output Headway") # run descriptive stats function

# plotting...
#ax = sns.distplot(headway) # create a plot
#plt.xlabel("Headway (s)")
#plt.ylabel("Frequency")
#plt.show() # show plot
