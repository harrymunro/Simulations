# Simulating occurence of customer train delays on the Piccadilly Line

import simpy
import random

sim_time_weeks = 520
sim_time_minutes = sim_time_weeks * 7 * 24 * 60
SIM_TIME = sim_time_minutes

num_incidents = 0
num_incidents_list = []

def incident_duration():
	duration = random.lognormvariate(1.59, 0.66)
	return duration

def source(env):
	while True:
		num_incidents_list.append(num_incidents)
		#print "\nTick"
		#print "Time = %d" % env.now
		prob = random.random() # sample a number from 0 to 1
		if prob < 9.026 * 10**(-4): # probability of customer related train delay in the next minute
			env.process(train_delay(env))
		#print "Tock"
		yield env.timeout(1)
		
def train_delay(env):
	global num_incidents
	#print "Incident has occurred"
	delay_duration = incident_duration()
	num_incidents += 1
	yield env.timeout(delay_duration)
	num_incidents -= 1
	#print "Incident has ended"
	
env = simpy.Environment()
env.process(source(env))
env.run(until=SIM_TIME)

#print num_incidents_list

zero = 0
one = 0
two = 0
three = 0
four = 0
more = 0

for i in num_incidents_list:
	if i == 0:
		zero += 1
	elif i == 1:
		one += 1
	elif i == 2:
		two += 1
	elif i == 3:
		three += 1
	elif i == 4:
		four += 1
	else:
		more += 1

print "\n%d minutes of simulation time (equivalent to %d weeks)" % (len(num_incidents_list), sim_time_weeks)
print "Control center had %d minutes of incident-free time" % zero
print "Control center spent %d minutes dealing with a single incident" % one
print "Control center spent %d minutes dealing with two incidents at once" % two
print "Control center spent %d minutes dealing with three incidents at once" % three
print "Control center spent %d minutes dealing with four incidents at once" % four
print "Control center spent %d minutes dealing with more than four incidents at once" % more
