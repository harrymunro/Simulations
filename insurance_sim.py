# -*- coding: utf-8 -*-
"""
Created on Mon Oct 23 13:42:05 2017

@author: harrymunro
"""

# Insurance simulation
# This calculates a written risk that causes a number of losses over a specified period
# Excess money is invested in the stock market at a 7% return
# The value of the account is charted out over a 10 year period

import simpy
import matplotlib.pyplot as plt
import numpy as np
import random

sim_time = 120 # months

account = 0
account_history = []
timestamp = []
inflation_rate = 0.03
equity_growth = 0.07

def write_risk(premium, frequency, loss, category, initial_loss, interval, occurrences):
	global account
	account = account + premium
	env.process(equity_investment(premium))
	while True:
		yield env.timeout(frequency)
		if category == "multiple":
			env.process(multiple_payments(loss, initial_loss, interval, occurrences))
		elif category == "single":
			account = account - loss

def multiple_payments(loss, initial_loss, interval, occurrences):
	global account
	print 'yes'
	account = account - initial_loss
	account_history.append(account)
	timestamp.append(env.now)
	for i in range(occurrences):
		yield env.timeout(interval)
		account = account - loss

def inflation_erosion():
	global account
	while True:
		yield env.timeout(1)
		account = account - account * inflation_rate/12

def equity_investment(amount):
	global account
	investment = amount
	while True:
		yield env.timeout(1)
		investment_change = investment * equity_growth/12
		account = account + investment_change
		investment = investment + investment_change
	
def print_results():
	global account
	while True:
		print "\nMonth %d" % env.now
		print "Balance: %r " % account
		yield env.timeout(1)
		
def update_account():
	while True:
		yield env.timeout(1)
		account_history.append(account)
		timestamp.append(env.now)

def inflation_drift():
	pass # add some code to change the annual rate of inflation
	
# setup environment
random.seed(random.random())
env = simpy.Environment()

# Start processes
env.process(print_results())
env.process(update_account())
env.process(inflation_erosion())
#env.process(inflation_drift())
env.process(write_risk(1000000, 6, 2000, "multiple", 10000, 1, 12)) 
#(premium, frequency, loss, category, initial_loss, interval, occurrences)

# Run simulation
env.run(until=sim_time)

plt.figure(1)
plt.scatter(timestamp, account_history)
plt.show()

def p_dice(target):
	rolls = []
   
	for n in range(1000000):
		roll = np.random.randint(1, 7)
		rolls.append(roll)
	n_successes = []
	for number in rolls:
		if number >= target:
			n_successes.append(True)
	return float(len_successes) / float(len(rolls))
