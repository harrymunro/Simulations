# Smart Toast
# Simplified in version 2 to only factor in toasting time


# Simulates the intelligent toaster

import random
import os.path
import numpy as np
import csv
from sklearn import linear_model


# Every time the toast is finished the user tells the toaster whether the toast was under-done, over-done or just right
# This data, along with the toast time and bread width is saved into the database along along with the users name
# A ML algorithm uses the database to determine the optimal toasting time for the given parameters in order to achieve "just-right" toast
# This means that we have a toaster that learns from user preferences

def file_len(fname):
	with open(fname) as f:
		for i, l in enumerate(f):
		pass
	return i + 1

while True:
# Need to ask which user from list or enter new user
# check if userlist exists
	userlist_exists = os.path.isfile("userlist.txt") # returns True if file exists
	if userlist_exists == True:
		text_file = open("userlist.txt", "r+b")
		lines = text_file.readlines()
		num_lines = len(lines)
		choice = False
		while choice == False:
			print "\nChoose from list of current users by entering number, or enter name of a new user."
			for n in range(num_lines):
				print "%d - %s" % (n, lines[n])
			user_choice = raw_input("Choice: ")
			try: 
				if int(user_choice) in range(num_lines+1):
					user_choice = lines[int(user_choice)]
					user_choice = user_choice[:-1]
				else:
					w = str(user_choice) + '\n'
					text_file.write(w)
			except ValueError:
				w = str(user_choice) + '\n'
				text_file.write(w)
			choice = True
		
	elif userlist_exists == False:
		text_file = open("userlist.txt", "w")
		user_choice = raw_input("Welcome! Enter your user name: ")
		text_file.write(str(user_choice)+"\n")
		
	text_file.close()
	
	filename = user_choice+".csv"

	toast_time = raw_input("\nEnter toast time in seconds: ")
	# Check whether CSV data file exists and read it, if not then create a default dataframe
	file_exists = os.path.isfile(filename) # returns True if file exists
	
	if file_exists == True and file_len(filename) > 2:
		with open(filename, 'rb') as csvfile:
			data = csv.reader(csvfile, delimiter=' ', quotechar='|')
			csvfile.close()
		# create input array
		first = np.loadtxt(filename, skiprows = 1, usecols = (2,))
		first = first.reshape(-1, 1)
		# create predictor array
		second = np.loadtxt(filename, skiprows = 1, usecols = (1,))
		second = second.reshape(-1, 1)
		
		blr = linear_model.LinearRegression()
		clf = blr.fit(first, second)
		toast_time = int(clf.predict(2))
	
	elif file_exists == False:
		with open(filename, 'a') as csvfile:
			data = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
			data.writerow(['User', 'Toast_Time', 'Satisfaction'])
			csvfile.close()

	raw_input("\nPress enter to start toasting!")
	
	print "\nToasted bread for %d seconds." % toast_time
	
	x = True 
	while x == True:
		satisfaction = int(raw_input("\nHow was your toast?\n0.Vastly under-toasted\n1.Slightly under-toasted\n2.Just right\n3.Slightly burnt\n4.Badly burnt\nEnter the number and press enter: "))
		if satisfaction in (0, 1, 2, 3, 4):
			x = False
		else:
			print "That wasn't a correct option, please choose again.\n"
			
	x = True		
	
	with open(filename, 'a') as csvfile:
		data = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
		data.writerow([user_choice, toast_time, satisfaction])
		csvfile.close()
    		
	with open(filename, 'rb') as f:
		reader = csv.reader(f)
		for row in reader:
			print row
		f.close()
