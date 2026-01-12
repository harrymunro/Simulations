import React, { useState, useEffect, useRef, useCallback } from 'react';

// Simulation parameters (matching SimPy example)
const PT_MEAN = 10.0;      // Avg. processing time in minutes
const PT_SIGMA = 2.0;      // Sigma of processing time
const MTTF = 300.0;        // Mean time to failure in minutes
const REPAIR_TIME = 30.0;  // Time it takes to repair a machine
const JOB_DURATION = 30.0; // Duration of other jobs
const NUM_MACHINES = 6;    // Reduced for better visualization
const SIM_SPEED = 50;      // ms per simulation minute

// Random number generators
const randomNormal = (mean, sigma) => {
  const u1 = Math.random();
  const u2 = Math.random();
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  return Math.max(1, mean + sigma * z);
};

const randomExponential = (mean) => {
  return -mean * Math.log(Math.random());
};

// Machine states
const WORKING = 'working';
const BROKEN = 'broken';
const WAITING = 'waiting';

// Repairman states
const REPAIRING = 'repairing';
const OTHER_JOB = 'other_job';
const IDLE = 'idle';

const MachineShopAnimation = () => {
  const [simTime, setSimTime] = useState(0);
  const [machines, setMachines] = useState([]);
  const [repairman, setRepairman] = useState({ state: IDLE, currentMachine: null, otherJobProgress: 0 });
  const [repairQueue, setRepairQueue] = useState([]);
  const [eventLog, setEventLog] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [totalParts, setTotalParts] = useState(0);
  const animationRef = useRef(null);
  const lastTimeRef = useRef(0);

  // Initialize machines
  const initializeMachines = useCallback(() => {
    const newMachines = Array.from({ length: NUM_MACHINES }, (_, i) => ({
      id: i,
      name: `Machine ${i + 1}`,
      state: WORKING,
      partsMade: 0,
      partProgress: 0,
      currentPartTime: randomNormal(PT_MEAN, PT_SIGMA),
      timeToFailure: randomExponential(MTTF),
      repairProgress: 0,
    }));
    setMachines(newMachines);
    setRepairman({ state: OTHER_JOB, currentMachine: null, otherJobProgress: 0, otherJobTime: JOB_DURATION });
    setRepairQueue([]);
    setSimTime(0);
    setEventLog([]);
    setTotalParts(0);
  }, []);

  useEffect(() => {
    initializeMachines();
  }, [initializeMachines]);

  const addEvent = useCallback((time, message, type = 'info') => {
    setEventLog(prev => [...prev.slice(-19), { time: time.toFixed(1), message, type }]);
  }, []);

  // Main simulation loop
  useEffect(() => {
    if (!isRunning) return;

    const simulate = (timestamp) => {
      if (!lastTimeRef.current) lastTimeRef.current = timestamp;
      const delta = (timestamp - lastTimeRef.current) * speed / SIM_SPEED;
      lastTimeRef.current = timestamp;

      if (delta > 0) {
        setSimTime(prev => prev + delta);

        setMachines(prevMachines => {
          const newMachines = [...prevMachines];
          let partsThisTick = 0;
          const newBroken = [];

          newMachines.forEach((machine, idx) => {
            if (machine.state === WORKING) {
              // Progress on current part
              machine.partProgress += delta;
              machine.timeToFailure -= delta;

              // Check for breakdown
              if (machine.timeToFailure <= 0) {
                machine.state = BROKEN;
                machine.timeToFailure = randomExponential(MTTF);
                newBroken.push(idx);
                addEvent(simTime + delta, `⚠️ ${machine.name} broke down!`, 'error');
              } else if (machine.partProgress >= machine.currentPartTime) {
                // Part completed
                machine.partsMade += 1;
                partsThisTick += 1;
                machine.partProgress = 0;
                machine.currentPartTime = randomNormal(PT_MEAN, PT_SIGMA);
              }
            } else if (machine.state === WAITING) {
              // Waiting for repair, do nothing
            }
          });

          if (partsThisTick > 0) {
            setTotalParts(prev => prev + partsThisTick);
          }

          // Add broken machines to repair queue
          if (newBroken.length > 0) {
            setRepairQueue(prev => [...prev, ...newBroken]);
          }

          return newMachines;
        });

        // Handle repairman
        setRepairman(prevRepairman => {
          const newRepairman = { ...prevRepairman };

          if (newRepairman.state === REPAIRING && newRepairman.currentMachine !== null) {
            // Continue repairing
            setMachines(prevMachines => {
              const newMachines = [...prevMachines];
              const machine = newMachines[newRepairman.currentMachine];
              if (machine) {
                machine.repairProgress += delta;
                if (machine.repairProgress >= REPAIR_TIME) {
                  // Repair complete
                  machine.state = WORKING;
                  machine.repairProgress = 0;
                  machine.partProgress = 0;
                  addEvent(simTime + delta, `✅ ${machine.name} repaired!`, 'success');
                  newRepairman.state = IDLE;
                  newRepairman.currentMachine = null;
                }
              }
              return newMachines;
            });
          } else if (newRepairman.state === OTHER_JOB) {
            // Working on other job
            newRepairman.otherJobProgress += delta;
            if (newRepairman.otherJobProgress >= newRepairman.otherJobTime) {
              newRepairman.otherJobProgress = 0;
              newRepairman.otherJobTime = JOB_DURATION;
              addEvent(simTime + delta, `📋 Other job completed`, 'info');
            }
          }

          // Check if there are machines to repair
          setRepairQueue(prevQueue => {
            if (prevQueue.length > 0 && (newRepairman.state === IDLE || newRepairman.state === OTHER_JOB)) {
              const machineToRepair = prevQueue[0];
              newRepairman.state = REPAIRING;
              newRepairman.currentMachine = machineToRepair;
              if (prevRepairman.state === OTHER_JOB) {
                addEvent(simTime + delta, `🔧 Repairman preempted to fix Machine ${machineToRepair + 1}`, 'warning');
              } else {
                addEvent(simTime + delta, `🔧 Repairman fixing Machine ${machineToRepair + 1}`, 'info');
              }
              setMachines(prevMachines => {
                const newMachines = [...prevMachines];
                if (newMachines[machineToRepair]) {
                  newMachines[machineToRepair].state = BROKEN;
                  newMachines[machineToRepair].repairProgress = 0;
                }
                return newMachines;
              });
              return prevQueue.slice(1);
            }
            return prevQueue;
          });

          // If idle and no repairs needed, do other job
          if (newRepairman.state === IDLE) {
            newRepairman.state = OTHER_JOB;
            newRepairman.otherJobProgress = 0;
            newRepairman.otherJobTime = JOB_DURATION;
          }

          return newRepairman;
        });
      }

      animationRef.current = requestAnimationFrame(simulate);
    };

    animationRef.current = requestAnimationFrame(simulate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isRunning, speed, addEvent, simTime]);

  const toggleSimulation = () => {
    if (!isRunning) {
      lastTimeRef.current = 0;
    }
    setIsRunning(!isRunning);
  };

  const resetSimulation = () => {
    setIsRunning(false);
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    initializeMachines();
  };

  const getStateColor = (state) => {
    switch (state) {
      case WORKING: return '#22c55e';
      case BROKEN: return '#ef4444';
      case WAITING: return '#f59e0b';
      default: return '#6b7280';
    }
  };

  const getRepairmanStateColor = (state) => {
    switch (state) {
      case REPAIRING: return '#3b82f6';
      case OTHER_JOB: return '#8b5cf6';
      case IDLE: return '#6b7280';
      default: return '#6b7280';
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            SimPy Machine Shop Simulation
          </h1>
          <p className="text-slate-400 text-sm">
            {NUM_MACHINES} machines producing parts • 1 repairman handling breakdowns & other jobs
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-center gap-4 mb-8 flex-wrap">
          <button
            onClick={toggleSimulation}
            className={`px-6 py-2 rounded-lg font-semibold transition-all ${
              isRunning 
                ? 'bg-amber-500 hover:bg-amber-600' 
                : 'bg-green-500 hover:bg-green-600'
            }`}
          >
            {isRunning ? '⏸ Pause' : '▶ Start'}
          </button>
          <button
            onClick={resetSimulation}
            className="px-6 py-2 rounded-lg font-semibold bg-slate-600 hover:bg-slate-500 transition-all"
          >
            ↻ Reset
          </button>
          <div className="flex items-center gap-2 bg-slate-800 px-4 py-2 rounded-lg">
            <span className="text-sm text-slate-400">Speed:</span>
            <input
              type="range"
              min="0.5"
              max="5"
              step="0.5"
              value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
              className="w-24"
            />
            <span className="text-sm font-mono w-8">{speed}x</span>
          </div>
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-slate-800 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-blue-400">{simTime.toFixed(0)}</div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">Sim Minutes</div>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-green-400">{totalParts}</div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">Parts Made</div>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-amber-400">{repairQueue.length}</div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">Repair Queue</div>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-purple-400">
              {machines.filter(m => m.state === WORKING).length}/{NUM_MACHINES}
            </div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">Working</div>
          </div>
        </div>

        {/* Main Visualization */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Machines Grid */}
          <div className="lg:col-span-2">
            <h2 className="text-lg font-semibold mb-4 text-slate-300">Production Floor</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {machines.map((machine) => (
                <div
                  key={machine.id}
                  className="bg-slate-800 rounded-xl p-4 border-2 transition-all duration-300"
                  style={{ borderColor: getStateColor(machine.state) }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-semibold">{machine.name}</span>
                    <div
                      className="w-3 h-3 rounded-full animate-pulse"
                      style={{ backgroundColor: getStateColor(machine.state) }}
                    />
                  </div>
                  
                  {/* Machine Icon */}
                  <div className="flex justify-center mb-3">
                    <div className="relative">
                      <svg viewBox="0 0 64 64" className="w-16 h-16">
                        {/* Machine body */}
                        <rect x="8" y="20" width="48" height="36" rx="4" 
                          fill={machine.state === BROKEN ? '#991b1b' : '#334155'} 
                          stroke={getStateColor(machine.state)} 
                          strokeWidth="2"
                        />
                        {/* Control panel */}
                        <rect x="12" y="24" width="16" height="12" rx="2" fill="#1e293b" />
                        {/* Lights */}
                        <circle cx="16" cy="30" r="2" fill={machine.state === WORKING ? '#22c55e' : '#6b7280'}>
                          {machine.state === WORKING && (
                            <animate attributeName="opacity" values="1;0.5;1" dur="0.5s" repeatCount="indefinite" />
                          )}
                        </circle>
                        <circle cx="24" cy="30" r="2" fill={machine.state === BROKEN ? '#ef4444' : '#6b7280'}>
                          {machine.state === BROKEN && (
                            <animate attributeName="opacity" values="1;0.3;1" dur="0.3s" repeatCount="indefinite" />
                          )}
                        </circle>
                        {/* Gears */}
                        <g transform="translate(44, 40)">
                          <circle cx="0" cy="0" r="8" fill="none" stroke="#64748b" strokeWidth="2" />
                          {machine.state === WORKING && (
                            <animateTransform
                              attributeName="transform"
                              type="rotate"
                              from="0"
                              to="360"
                              dur="1s"
                              repeatCount="indefinite"
                            />
                          )}
                          {[0, 60, 120, 180, 240, 300].map((angle, i) => (
                            <rect
                              key={i}
                              x="-2"
                              y="-10"
                              width="4"
                              height="6"
                              fill="#64748b"
                              transform={`rotate(${angle})`}
                            />
                          ))}
                        </g>
                        {/* Conveyor */}
                        <rect x="8" y="52" width="48" height="4" fill="#475569" />
                      </svg>
                      
                      {/* Repair overlay */}
                      {repairman.currentMachine === machine.id && (
                        <div className="absolute -top-2 -right-2">
                          <span className="text-2xl animate-bounce">🔧</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Status */}
                  <div className="text-center mb-2">
                    <span 
                      className="text-xs font-medium px-2 py-1 rounded-full"
                      style={{ 
                        backgroundColor: getStateColor(machine.state) + '33',
                        color: getStateColor(machine.state)
                      }}
                    >
                      {machine.state.toUpperCase()}
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="mb-2">
                    {machine.state === WORKING && (
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-green-500 transition-all duration-100"
                          style={{ width: `${(machine.partProgress / machine.currentPartTime) * 100}%` }}
                        />
                      </div>
                    )}
                    {machine.state === BROKEN && repairman.currentMachine === machine.id && (
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 transition-all duration-100"
                          style={{ width: `${(machine.repairProgress / REPAIR_TIME) * 100}%` }}
                        />
                      </div>
                    )}
                  </div>

                  {/* Parts counter */}
                  <div className="text-center text-sm text-slate-400">
                    <span className="font-mono">{machine.partsMade}</span> parts
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Panel */}
          <div className="space-y-6">
            {/* Repairman */}
            <div>
              <h2 className="text-lg font-semibold mb-4 text-slate-300">Repairman</h2>
              <div 
                className="bg-slate-800 rounded-xl p-4 border-2 transition-all"
                style={{ borderColor: getRepairmanStateColor(repairman.state) }}
              >
                <div className="flex items-center gap-4">
                  <div className="text-4xl">
                    {repairman.state === REPAIRING ? '🔧' : repairman.state === OTHER_JOB ? '📋' : '😴'}
                  </div>
                  <div className="flex-1">
                    <div className="font-semibold mb-1">
                      {repairman.state === REPAIRING 
                        ? `Repairing Machine ${repairman.currentMachine + 1}` 
                        : repairman.state === OTHER_JOB 
                          ? 'Doing Other Jobs' 
                          : 'Idle'}
                    </div>
                    {repairman.state === REPAIRING && repairman.currentMachine !== null && (
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 transition-all duration-100"
                          style={{ 
                            width: `${(machines[repairman.currentMachine]?.repairProgress / REPAIR_TIME) * 100}%` 
                          }}
                        />
                      </div>
                    )}
                    {repairman.state === OTHER_JOB && (
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-purple-500 transition-all duration-100"
                          style={{ 
                            width: `${(repairman.otherJobProgress / repairman.otherJobTime) * 100}%` 
                          }}
                        />
                      </div>
                    )}
                  </div>
                </div>
                {repairQueue.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-700">
                    <div className="text-xs text-slate-400 mb-1">Waiting for repair:</div>
                    <div className="flex gap-1 flex-wrap">
                      {repairQueue.map((id) => (
                        <span key={id} className="text-xs bg-red-900 text-red-300 px-2 py-0.5 rounded">
                          M{id + 1}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Event Log */}
            <div>
              <h2 className="text-lg font-semibold mb-4 text-slate-300">Event Log</h2>
              <div className="bg-slate-800 rounded-xl p-4 h-64 overflow-y-auto">
                {eventLog.length === 0 ? (
                  <div className="text-slate-500 text-center text-sm">
                    Start the simulation to see events...
                  </div>
                ) : (
                  <div className="space-y-1">
                    {eventLog.map((event, idx) => (
                      <div 
                        key={idx} 
                        className={`text-xs font-mono ${
                          event.type === 'error' ? 'text-red-400' :
                          event.type === 'success' ? 'text-green-400' :
                          event.type === 'warning' ? 'text-amber-400' :
                          'text-slate-400'
                        }`}
                      >
                        <span className="text-slate-600">[{event.time}]</span> {event.message}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="mt-8 flex justify-center gap-6 flex-wrap text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-slate-400">Working</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-slate-400">Broken</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span className="text-slate-400">Being Repaired</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-purple-500" />
            <span className="text-slate-400">Repairman: Other Jobs</span>
          </div>
        </div>

        {/* Footer info */}
        <div className="mt-6 text-center text-xs text-slate-500">
          Based on the SimPy Machine Shop example • MTTF: {MTTF} min • Repair Time: {REPAIR_TIME} min • Avg Part Time: {PT_MEAN}±{PT_SIGMA} min
        </div>
      </div>
    </div>
  );
};

export default MachineShopAnimation;
