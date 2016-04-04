"""
Scenario:
  A system has *n* identical pieces of equipment. Each piece of equipment breaks down
  periodically. Repairs are carried out by *m* repairmen. Broken pieces of equipment
  preempt repairmens other tasks. The system works continuously.
  Assumes an exponential distribution for time to failure, repair time and logistics delay. Base units are minutes.
  Code is based on the machine shop example found in the simpy readthedocs.
  The principle difference is the analysis I have included at the end plus the use of extra exponential distributions.
  Machine shop example found here: http://simpy.readthedocs.org/en/latest/examples/machine_shop.html
"""
import random
import simpy
import numpy as np

RANDOM_SEED = 42
MTTF = 250.0           # Mean time to failure in hours
BREAK_MEAN = 1 / (MTTF * 60.0)  # Param. for expovariate distribution
MTTR = 300.0
MEAN_REPAIR_TIME = 1 / MTTR     # Time it takes to repair a machine in minutes
MLT = 120.0
MEAN_LOGISTICS_TIME = 1 / MLT
JOB_DURATION = 60.0    # Duration of other jobs in minutes
NUM_MACHINES = 12     # Number of signals in the system
NUM_REPAIRMEN = 2	# Number of staff members
WEEKS = 52              # Simulation time in weeks
SIM_TIME = WEEKS * 7 * 24 * 60  # Simulation time in minutes


def time_to_failure():
    """Return time until next failure for a machine."""
    return random.expovariate(BREAK_MEAN)

def REPAIR_TIME():
    """Return time until next failure for a machine."""
    return random.expovariate(MEAN_REPAIR_TIME) + random.expovariate(MEAN_LOGISTICS_TIME)


class Machine(object):
    """A machine operates and occasionally breaks.

    If it breaks, it requests a *repairman* and continues the production
    after the it is repaired.

    A machine has a *name* and a numberof *parts_made* thus far.

    """
    def __init__(self, env, name, repairman):
        self.env = env
        self.name = name
        self.uptime = 0
        self.downtime = 0
        self.broken = False

        # Start "working" and "break_machine" processes for this machine.
        self.process = env.process(self.working(repairman))
        env.process(self.break_machine())

    def working(self, repairman):
        """Produce parts as long as the simulation runs.

        While making a part, the machine may break multiple times.
        Request a repairman when this happens.

        """
        while True:
            # Start operating
            done_in = 5
            while done_in:
                try:
                    # Working on the operation
                    start = self.env.now
                    yield self.env.timeout(done_in)
                    done_in = 0  # Set to 0 to exit while loop.

                except simpy.Interrupt:
                    self.broken = True
                    start_break = self.env.now
                    done_in -= self.env.now - start  # How much time left?

                    # Request a repairman. This will preempt its "other_job".
                    with repairman.request(priority=1) as req:
                        yield req
                        repair = REPAIR_TIME()
                        yield self.env.timeout(repair)
                    self.downtime += self.env.now - start_break

                    self.broken = False

            # Part is done.
            self.uptime += 5

    def break_machine(self):
        """Break the machine every now and then."""
        while True:
            yield self.env.timeout(time_to_failure())
            if not self.broken:
                # Only break the machine if it is currently working.
                self.process.interrupt()


def other_jobs(env, repairman):
    """The repairman's other (unimportant) job."""
    while True:
        # Start a new job
        done_in = JOB_DURATION
        while done_in:
            # Retry the job until it is done.
            # It's priority is lower than that of machine repairs.
            with repairman.request(priority=2) as req:
                yield req
                try:
                    start = env.now
                    yield env.timeout(done_in)
                    done_in = 0
                except simpy.Interrupt:
                    done_in -= env.now - start


# Setup and start the simulation
print('Equipment Availability Analysis.')
random.seed(RANDOM_SEED)  # This helps reproducing the results

# Create an environment and start the setup process
env = simpy.Environment()
repairman = simpy.PreemptiveResource(env, capacity= NUM_REPAIRMEN)
machines = [Machine(env, 'Machine %d' % i, repairman)
        for i in range(NUM_MACHINES)]
env.process(other_jobs(env, repairman))

# Execute!
env.run(until=SIM_TIME)

# Analyis of results
print('Maintenance analysis after %s weeks:') % WEEKS
availability = []
for machine in machines:
    print('%s operational availability of %r.' % (machine.name, machine.uptime / (machine.downtime + machine.uptime)))
    availability.append(machine.uptime / (machine.downtime + machine.uptime))
    
# Overall operational availability assumes the machines are arranges in series in block diagram mode.
print ('Overall operational availability of %r.') % np.product(availability)
