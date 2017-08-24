## Depot Model simulation
# Runs in 15 minute slots
"""
This model is template that utilises simpy to simulate a depot.
A depot has a series of facilities that can carry out maintenance activities.
A fleet of trains (or whatever else) has a set of maintenance requirements.
There is a timetable that determines how many trains need to be available.
The timetable is prioritised over maintenance, until maintenance falls past its tolerance.
Shunting windows are defined. 
Maintenance cannot be started while trains are being "injected" into service.
"""

import math
import random
import simpy
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
#import seaborn as sns
import pandas as pd
import time
import logging
import collections
from collections import OrderedDict

logger=logging.getLogger()
hnd = logging.FileHandler('maintenance_outputs.log', mode='wb')
logger.addHandler(hnd)
logger.warning( "Fleet Exam_name start start_day start_time finish finish_day finish_time  timetable_trains_needed number_of_trains_in_depot tolerance road time_train_seized tolerance_left")

start_time = time.time()

ACTIVE_MAINTENANCE = {}
## Maintenance data dictionary
activities = ['activity']
# Interval type (service hour, service day, calendar day or mileage) | interval time | tolerance time | exam length (15 minute slots) | by unit/train | staff requirement
maintenance_data_input = {'activity': ['service hour', 200, 60, 5, 'by train', 3]}
							
# Timetable
timetable = np.loadtxt('timetable.csv', delimiter = ',', skiprows = 1).tolist()
injection_window = np.loadtxt('shunting.csv', delimiter = ',', skiprows = 1, dtype = 'string').tolist()
#reception_window = np.load('reception_window.npy').tolist()


# Initial conditions (global variables)
peak_time = False
weekday = True
day = "Monday"
injection = False
reception = True
peak = False

# Simulation time setup
weeks = 6
SIM_TIME = 672 * weeks

# Initial staff use
staff = 0

# Maintenance logging
live_maintenance_requests = 0
maintenance_requests = []
maintenance_completes = []

# Train availability logging
peak_available_trains = []

# Assumptions
wheel_weekends_only = True


# Fleet Variables
fleet_size = 150
mon_thurs_mileage = 40000 
fri_mileage = 40000 
sat_mileage = 40000 
sun_mileage = 40000 

##### MILEAGES PER TRAIN #####
train_mileage_per_week = ((mon_thurs_mileage * 4) + fri_mileage + sat_mileage + sun_mileage) / fleet_size
train_mileage_per_day = train_mileage_per_week / 7
train_weekday_daily_mileage = (((mon_thurs_mileage * 4) + fri_mileage) / 5) / fleet_size
train_weekend_daily_mileage = ((sat_mileage + sun_mileage) / 2) / fleet_size

# Fleet live data
timetable_requirement = 0
available_to_maintain = fleet_size - timetable_requirement
trains_in_depot = 10 # number in the depot for casualty
trains_available = fleet_size - trains_in_depot

#### Setting weekday_peak and week end peak timetable
weekday_peak = 120 # 5 days per week
weekend_peak = 80.0 # 2 days per week

# add more data if saturday and sunday have different peak trains on line
weekday_percentage_in_service = weekday_peak / fleet_size # percentage of fleet that gets in service during week days
weekend_percentage_in_service = weekend_peak / fleet_size # percentage of fleet that gets in service during weekends
service_day_rate = ((weekday_percentage_in_service * 5) + (weekend_percentage_in_service * 2)) / 7 # the MAGIC NUMBER which tells us the probability of a day being a service day
service_hour_per_calendar_day = service_day_rate * 17 

# weekday update
def weekday(env):
	global weekday
	global day
	while True:
		weekday = True
		day = "Monday"
		yield env.timeout(1 * 24 * 4)
		day = "Tuesday"
		yield env.timeout(1 * 24 * 4)
		day = "Wednesday"
		yield env.timeout(1 * 24 * 4)
		day = "Thursday"
		yield env.timeout(1 * 24 * 4)
		day = "Friday"
		yield env.timeout(1 * 24 * 4)
		day = "Saturday"
		weekday = False
		yield env.timeout(1 * 24 * 4)
		day = "Sunday"
		yield env.timeout(1 * 24 * 4)
		
def peak_update(env):
# mornign peak defined from the depot as 05:00 to 10:00 and afternoon 16:00-19:00
	global peak_time
	global peak
	while True: #monday to Friday
		for day in range(0, 5): 
			peak_time = False
			peak =False
			yield env.timeout(5 * 4)
			peak_time = True
			peak = True
			yield env.timeout(5 * 4)
			peak = False
			peak_time = False
			yield env.timeout(6 * 4)
			peak = True
			peak_time = True
			yield env.timeout(3 * 4)
			peak = False
			peak_time = True		
			yield env.timeout(0.5 * 4)
			peak=False
			peak_time = False
			yield env.timeout(4.5 * 4)

		#week end
		peak = False
		peak_time = False
		yield env.timeout(48 * 4)
	

# interval time function
def interval(time):
	#result = random.expovariate(1.0 / time) # use for fleet maintenance model
	result = time # use for individual train maintenance model
	return result
	
def normal_distribution(time):
	n = random.gauss(time, time/4)
	return n

def update_timetable_requirement(env):
	global timetable_requirement
	global available_to_maintain
	global injection
	global reception
	global trains_available
	while True:
		timenow = env.now % len(timetable)
		timetable_requirement = timetable[timenow]
		available_to_maintain = fleet_size - timetable_requirement
		injection = injection_window[timenow]
		#reception = reception_window[timenow]
		trains_available = fleet_size - trains_in_depot
		if trains_available < 0:
			print('No trains available')
			break
			#trains_available = 0
		yield env.timeout(1)

class Train(object):
	def __init__(self, env, depot, number, age, fleet_size, fleet_name, mileage):
		self.env = env
		self.fleet_name = fleet_name
		self.train_age = age # age of train in service days: helps randomise maintenance schedule
		self.train_number = number
		self.service_days = age * service_day_rate
		self.mileage = mileage
		self.in_maintenance=False
		# kickoff maintenance requirements
		for activity in activities:
			env.process(self.maintenance_activity(activity, self.fleet_name, maintenance_data_input[activity][1], maintenance_data_input[activity][2], maintenance_data_input[activity][3] * 4, maintenance_data_input[activity][5], depot, maintenance_data_input[activity][0], maintenance_data_input[activity][4], fleet_size))
					
		#env.process(self.counter())		
		#env.process(self.printer())	
		
	def counter(self):
		while True:
			self.mileage += 100
			yield self.env.timeout(1)
	def printer(self):
		while True:	
			print self.mileage
			yield self.env.timeout(4*24)
			
	
	# maintenance activity process				
	def maintenance_activity(self, exam_name, fleet_name, service_interval, tolerance, exam_length, staff_requirement, depot, interval_type, maintenance_type, fleet_size):
			
		fleet_name_number = "%s No. %d" % (self.fleet_name, self.train_number)
		print "Fleet %s exam %s has exam length %d and occurs every %d service days (tolerance = %d)" % (fleet_name_number, exam_name, exam_length, service_interval, tolerance)
		
		if interval_type == 'service day':
			service_interval = (service_interval / service_day_rate)# service interval in days
			tolerance = (tolerance / service_day_rate) # tolerance in days
		elif interval_type == 'calendar day':
			service_interval = service_interval# # service interval in days
			tolerance = tolerance # tolerance in days
		elif interval_type =='mileage':
			service_interval = service_interval / train_mileage_per_day # days until repair needed
			tolerance = tolerance / train_mileage_per_day # tolerance in days
		elif interval_type == 'service hour':
			service_interval=service_interval/service_hour_per_calendar_day
			tolerance = tolerance / service_hour_per_calendar_day
		else:
			print "Warning: service interval not properly assigned"
		
		time_between_repairs = service_interval * 4 * 24 # convert days to 15 minute time steps
		tolerance = tolerance * 4 * 24 # tolerance time in 15 minute time steps
					
		# generate maintenance requests with an initial request based on present train age
		days_to_first_maintenance = service_interval - (self.train_age % service_interval)
		yield self.env.timeout(days_to_first_maintenance * 4 * 24)
		mro=maintenance_request_object(self.env, fleet_name, exam_name, exam_length, staff_requirement, depot, tolerance, maintenance_type,self) # create a maintenance request	
		# now generate maintenance requests at specific intervals until the rest of time
		while True:
			
			while not mro.maintenance_complete:
			
				yield self.env.timeout(1) 
			
			yield self.env.timeout(interval(time_between_repairs)) # time between interval
			# time to carry out a maintenance activity!!
			
			mro=maintenance_request_object(self.env, fleet_name, exam_name, exam_length, staff_requirement, depot, tolerance, maintenance_type,self) # create a maintenance request
			
class maintenance_request_object(Train):
	def __init__(self, env, fleet_name, exam_name, exam_length, staff_requirement, depot, tolerance, maintenance_type, train=None):
		self.env = env
		self.exists = True
		self.train_seized = False
		self.exam_name = exam_name
		self.tolerance_exceeded = False
		self.can_start_maintenance = False
		self.maximum_future_timetable_requirement = timetable_requirement
		self.maximum_future_trains_to_maintain = available_to_maintain
		self.in_depot = True
		self.train=train
		self.request_time = env.now
		self.maintenance_complete= False
		# state updates
		
		if self.train.train_number not in ACTIVE_MAINTENANCE:
			ACTIVE_MAINTENANCE[self.train.train_number] = {}
		if exam_name not in ACTIVE_MAINTENANCE[self.train.train_number]:
			ACTIVE_MAINTENANCE[self.train.train_number][exam_name] = []
			
		ACTIVE_MAINTENANCE[self.train.train_number][exam_name].append(self)
		
		env.process(self.tolerance_countdown(tolerance, exam_name))
		env.process(self.timetable_lookahead(exam_length, exam_name))
		# maintenance activity
		env.process(self.maintenance_request(fleet_name, exam_name, exam_length, staff_requirement, depot, tolerance, maintenance_type))
				
	def tolerance_countdown(self, tolerance, exam_name):
		yield self.env.timeout(tolerance)
		self.tolerance_exceeded = True
		self.train_seized = True
		

	def timetable_lookahead(self, exam_length, exam_name):
#This continually looks forward in time and asks:
#'What is the minimum number of trains that will be available to maintain 
#during the time it takes to carry out this maintenance activity.'
#This allows the activity to be deferred (if it is within tolerance).
#So that the timetable will not be disrupted unnecessarily.
		while self.can_start_maintenance == False:
			# SMART PLANNING

			timenow = self.env.now
			current_timetable_position = int(self.env.now % len(timetable))
			exam_finish_timetable_position = int((timenow + exam_length) % len(timetable))
			# need to lookahead at all timetable slots from now to end of exam
			# if there will be a shortfall of trains then do not carry out maintenance!
			future_timetable_requirements = []
			if current_timetable_position < exam_finish_timetable_position:
				for step in range(current_timetable_position, exam_finish_timetable_position):
					future_timetable_requirements.append(timetable[step])
			elif current_timetable_position >= exam_finish_timetable_position:
				for step in range(current_timetable_position, len(timetable)):
					future_timetable_requirements.append(timetable[step])
				for step in range(0, exam_finish_timetable_position):
					future_timetable_requirements.append(timetable[step])
			else:
				print 'Warning: Invalid timetable position'
			self.maximum_future_timetable_requirement = np.max(future_timetable_requirements)
			self.maximum_future_trains_to_maintain = (fleet_size - self.maximum_future_timetable_requirement) # forward looking
			yield self.env.timeout(1)			
			
	def maintenance_request(self, fleet_name, exam_name, exam_length, staff_requirement, depot, tolerance, maintenance_type):
		global trains_in_depot
		global staff
		global available_to_maintain
		global live_maintenance_requests
		
		live_maintenance_requests += 1
		
		needs_maintenance = True # I need to do some maintenance!
	
		tolerance_time = env.now + tolerance # when the tolerance is
		
		#print 'starting %s maintenance at time %d' % (exam_name, env.now)
	
		# now maintenance has to begin the train will ask for a road (and sit in stabling "out of service" if not!)
		maintenance_requests.append(env.now) # log when the activity was requested
		
		while self.can_start_maintenance == False:
				# try and start maintenance
				if ((injection == False and trains_in_depot < self.maximum_future_trains_to_maintain and trains_in_depot < available_to_maintain) or self.tolerance_exceeded == True) and not self.train.in_maintenance:
						self.can_start_maintenance = True # exit while loop
						break	
				elif self.can_start_maintenance == False: # if need to go forward another step
					yield self.env.timeout(1) # go forward one step	
				else:
					print(self.can_start_maintenance)
					print 'Warning: while loop for maintenance not exited when it should have'
				
		self.train_seized = True
		self.train.in_maintenance=True
		#log the data from when the train is seized
		total_timetable_train_start=fleet_size-self.maximum_future_trains_to_maintain
		time_train_seized=env.now
		trains_in_depot_start=trains_in_depot
		time_left=(tolerance_time-time_train_seized)/4/24
		live_maintenance_requests -= 1
		trains_in_depot += 1
		#get the road
		req = yield depot.get(lambda req: req['id'] in exam_reference[exam_name])
		#log the road used
		road_used=req
		
		depot_destination = req['id'][0]
		
		# check if injection window is true and if not then don't start maintainance until it is False!
		if injection == True:
			while True:
				if injection == True:
					yield self.env.timeout(1)
				elif injection == False:
					break
				else:
					print 'Warning strange condition for injection'
					
		
		staff += staff_requirement # staff get reserved for job
		
		start_of_maintenance=env.now
		start_day=day
		tolerance_exceeded=self.tolerance_exceeded
		start_time=(env.now/24/4-math.trunc(env.now/24/4))*24
		
		yield self.env.timeout(exam_length)
		end_time=(env.now/24/4-math.trunc(env.now/24/4))*24
		end_of_maintenance=env.now
		end_day=day
		
		trains_in_depot -= 1 # train has finished maintenance
		
		staff -= staff_requirement # staff have stopped working on job
		
		yield depot.put(req) # free the road
				
		maintenance_completes.append(env.now) # log when the activity was completed
		self.maintenance_complete=True
		self.train.in_maintenance=False
		
		logger.warning( "%d %s %d %s %.2f %d %s %.2f %d %d %d %s %d %.2f" % (self.train.train_number, exam_name, start_of_maintenance, start_day, start_time, end_of_maintenance, end_day, end_time, total_timetable_train_start, trains_in_depot_start, tolerance_exceeded, road_used, time_train_seized, time_left))
		
		if self in ACTIVE_MAINTENANCE[self.train.train_number][exam_name]:
			
			ACTIVE_MAINTENANCE[self.train.train_number][exam_name].remove(self)
	
		""" 
		The code below used to record one unit maintained for "by unit"
		and two units maintained for "by train" maintenance.
		"""
		if maintenance_type == 'by unit':
			maintainance_dictionary.append({exam_name: 1}) # one unit maintained (changed to 2 -> 15/03/2017)
		elif maintenance_type == 'by train':
			maintainance_dictionary.append({exam_name: 2}) # two units maintained
			
				
def results_recorder(env):
	while True:
		# road utilisation updating
		utilisation_update('road_name', road_name)
		
		if injection == False and reception == True:
			shunting_status = 'RECEPTION'
		elif injection == True and reception == False:
			shunting_status = 'INJECTION'
		else:
			shunting_status = 'INTER'
						
		spare_trains = fleet_size - trains_in_depot
		trains_in_service = spare_trains - timetable_requirement
		if trains_in_service >= 0:
			trains_in_service = timetable_requirement
		elif trains_in_service < 0:
			trains_in_service = timetable_requirement + (spare_trains - timetable_requirement)

		output_dictionary.append({'DAY': day, 'WEEKDAY': weekday, 'ROADS_FREE': len(depot.items), 'ROADS_FREE_LIST': depot.items[:], 
				'STAFF_IN_USE': staff, 'trains_in_depot': trains_in_depot, 'TIMETABLE_REQUIREMENT': timetable_requirement,
				'SHUNTING_STATUS': shunting_status, 'TOTAL_TIME': env.now, 'WEEK_TIME': (env.now % 672), 
				'TRAINS_AVAILABLE': (trains_available),'SPARE_TRAINS': ((fleet_size - trains_in_depot) -timetable_requirement), 'PEAK': peak, 'MAINTENANCE_REQUESTS': live_maintenance_requests, 
				'TRAINS_IN_SERVICE': trains_in_service})

		yield env.timeout(1)

		
# function tp update road utilisation stats
def utilisation_update(road_name, road_list):
	if {'id': road_name} in depot.items:
		road_list.append(0) # not in use
	else:
		road_list.append(1) # in use

# Progress update		
def check_progress(env):
	while True:
		week_number = env.now / 672
		year_number = env.now / (672 * 52)
		print "Processing week %d, year %d" % (week_number, year_number)
		yield env.timeout(4*24*7)

# empty lists to be filled with dictionaries to convert later into dataframes
output_dictionary = []
maintainance_dictionary = []
post_processing_results = []

# Create environment  
SEED = random.random()  
random.seed(SEED)
env = simpy.Environment()

# Define number of roads at Stratford that can be used for maintenance
depot = simpy.FilterStore(env, capacity = 17)

# Define the names of the specific roads (needed for matching with maintenance reference matrix)
depot.put({'id': 'road_name'}) # example road


# empty results lists for road utilisation tracking
road_name = []


# maintenance reference matrix: list the roads that can be used for each exam
exam_reference = OrderedDict()
exam_reference['activity'] =  ['road_name']

print exam_reference
# Kick start the state updating processes in the simulation
env.process(update_timetable_requirement(env))
env.process(peak_update(env))
env.process(results_recorder(env))
env.process(weekday(env))

# Generate trains
for n in range(0, fleet_size):
	# Random train ages
	#age = np.random.random() * 1100 # random age between 0 and 1100 days
	
	# Evenly spread out train ages
	step = 365.0 / fleet_size # enable this to evenly spread out the train age
	age = n * step # enable this to evenly spread out the train age
	
	mileage = age * train_mileage_per_day * service_day_rate # KM
	Train(env, depot, n+1, age, 1, '95TS', mileage)

# Start the simulation
env.process(check_progress(env))
env.run(until=SIM_TIME)

# Measure simulation time
end_time = time.time() - start_time
print "Simulation took: %d seconds" % end_time

# create dataframe
df = pd.DataFrame(output_dictionary)
maintainance_df = pd.DataFrame(maintainance_dictionary)
df.to_csv('results_outputs.csv', index=False)
post_processing_results.append({'MEAN_REQUESTS_PER_WEEK': len(maintenance_requests) / weeks,
								'MEAN_FULFILLED_PER_WEEK': len(maintenance_completes) / weeks,
								'MAINTENANCE_PERFORMANCE': float(len(maintenance_completes)) / len(maintenance_requests) * 100,
								'MEAN_STAFF_HOURS_PER_WEEK': np.sum(df['STAFF_IN_USE']) / weeks,
								'MEAN_NUMBER_TRAINS_IN_DEPOT': np.mean(df['trains_in_depot'])})

post_processing_df = pd.DataFrame(post_processing_results)
print post_processing_df

# Weekly counting
trains_maintained_per_week = []
units_maintained_per_week = []
for week in range(weeks):
	time_start = week * 672
	time_end = (week + 1) * 672
	trains_maintained_per_week.append(sum(1 for x in maintenance_completes if x > time_start and x < time_end))
	units_maintained_per_week.append(sum(2 for x in maintenance_completes if x > time_start and x < time_end))
	
roads = [road_name]
road_names = ['road_name']
utilisation = []
i=0
for road in roads:
	u = (float(np.sum(road)) / SIM_TIME) * 100
	utilisation.append(u)
	print "Road utilisation  = %d percent" % u


for tn, train_data in ACTIVE_MAINTENANCE.items():
	for exam_name, data in train_data.items():
		
		if data:
			
			print "Outstanding requests:", tn, exam_name, len(data), [d.request_time for d in data] 
#exit(0)

plt.figure(3)
ax = plt.subplot(111)
#plt.plot(idle_trains, label = 'Idle Trains')
#plt.plot(df['trains_in_depot'], label = 'Trains in Depot being Maintained')
ax.plot(df['STAFF_IN_USE'], label = 'LU Staff in Use')
#ax.plot(available_to_maintain_data, label = 'Trains Available to Maintain')
ax.plot(df['TIMETABLE_REQUIREMENT'], label = 'Timetable Requirement')
ax.plot(df['TRAINS_AVAILABLE'], label = 'Available Trains')
ax.plot(df['MAINTENANCE_REQUESTS'], label = 'Maintenance Requests')
ax.plot(df['TRAINS_IN_SERVICE'], label = 'Trains in Service')
plt.xlabel('Simulation Time (15 minute steps)')
plt.title('Stochastic Simulation Output')
#ax.plot(ability_to_meet_timetable, label = 'Timetable Spare Trains or Shortfall')
# Shrink current axis by 20%
box = ax.get_position()
ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
ax.legend(loc = 'center left', bbox_to_anchor = (1, 0.5))

#print df
#print '\nMean statistics:'
#print df.mean()
#print '\nStandard deviation statistics:'
#print df.std()
print '\nMorning peak statistics:'
print df.groupby('PEAK').describe()

print "\nTrain availability statistics..."
shortfalls = []
for spare in df['SPARE_TRAINS']:
	if spare < 0:
		shortfalls.append(spare)
x = 100 - (float(len(shortfalls)) / len(df['SPARE_TRAINS']) * 100)
print "The timetable was met %0.1f percent of the time." % x

#plt.figure(5)
#plt.scatter(df['STAFF_IN_USE'], df['trains_in_depot'])

#thefile = open('trains_maintained_per_Week.txt', 'w')
#for item in trains_maintained_per_week:
#	thefile.write("%d\n" % item)

df.to_csv('simulation_output.csv')

#print df.std()

print (maintainance_df.sum() / weeks)

plt.tight_layout()
plt.show()


# summary statistics
mean_trains_in_service = df['TRAINS_IN_SERVICE'].quantile(q = 0.99)
print "95th percentile trains in service: %d" % mean_trains_in_service
mean_timetable_requirement = np.percentile(timetable, 99)
print "95th percentile timetable requirement: %d" % mean_timetable_requirement

correlation = np.corrcoef(df['TRAINS_IN_SERVICE'], df['TIMETABLE_REQUIREMENT'])
print correlation

