# solver.py - UPDATED FOR MULTI-RESOURCE SCHEDULING

from ortools.sat.python import cp_model
import pandas as pd
from datetime import datetime, timedelta

def find_optimal_schedule(scenarios, personnel, start_date_str):
    """Calculates the optimal multi-resource UAT schedule using CP-SAT."""
    
    model = cp_model.CpModel()
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    
    people_map = {p['name']: i for i, p in enumerate(personnel)}
    
    # --- Store ALL Sub-tasks (One per required workstream) ---
    all_subtasks = []
    
    # Earliest start/Latest end: Assuming a 60-day horizon (1440 hours) for long tasks
    earliest_start = 0 
    horizon = 60 * 24 

    # --- 1. Create Model Variables for Each Scenario Component ---
    
    for scenario_idx, scenario in enumerate(scenarios):
        scenario_name = scenario['name']
        duration_hours = int(scenario['duration_hours'])
        
        # All sub-tasks for this scenario must share the SAME start/end time.
        start_var = model.NewIntVar(earliest_start, horizon, f'{scenario_name}_start')
        end_var = model.NewIntVar(earliest_start, horizon, f'{scenario_name}_end')
        
        # Link start, duration, and end (Mandatory interval)
        model.Add(end_var == start_var + duration_hours)

        for ws_idx, required_workstream in enumerate(scenario['required_workstreams']):
            task_suffix = f'_{scenario_idx}_{ws_idx}'
            
            # --- Sub-task Constraints (Resource Selection) ---
            
            # 1. Resource Variable: Which person is assigned (index)
            assigned_person_var = model.NewIntVar(0, len(personnel) - 1, 'person' + task_suffix)

            # 2. Constraint: Workstream Requirement
            valid_people_indices = [
                people_map[p['name']] 
                for p in personnel 
                if p['workstream'] == required_workstream
            ]
            
            # Restrict the person variable to those in the required workstream
            if valid_people_indices:
                model.AddAllowedAssignments([assigned_person_var], [(idx,) for idx in valid_people_indices])
            else:
                 # If no person exists for a required workstream, this makes the problem infeasible
                 print(f"ERROR: No personnel found for workstream: {required_workstream}")

            # 3. Create Interval Variable for No-Overlap Constraint
            # Note: We must use a fixed duration here, linked to the shared start/end.
            interval = model.NewIntervalVar(start_var, duration_hours, end_var, 'interval' + task_suffix)
            
            # Store the sub-task for solver processing and output
            all_subtasks.append({
                'scenario_name': scenario_name,
                'workstream': required_workstream,
                'duration': duration_hours,
                'start': start_var,
                'end': end_var,
                'person': assigned_person_var,
                'interval': interval
            })

    # --- 2. Constraint: No Two Tasks on the Same Person at the Same Time ---
    
    person_to_intervals = [[] for _ in personnel]

    for subtask in all_subtasks:
        
        # Create Boolean variables to link the subtask to its assigned person
        for person_index in range(len(personnel)):
            is_assigned_to_person = model.NewBoolVar(f'is_subtask_{subtask["scenario_name"]}_to_person_{person_index}')
            
            # Link Boolean to person variable
            model.Add(subtask['person'] == person_index).OnlyEnforceIf(is_assigned_to_person)
            model.Add(subtask['person'] != person_index).OnlyEnforceIf(is_assigned_to_person.Not())

            # Create an Optional Interval: active only if the person is assigned
            optional_interval = model.NewOptionalIntervalVar(
                subtask['start'], 
                subtask['duration'], 
                subtask['end'], 
                is_assigned_to_person, 
                f'optional_interval_{subtask["scenario_name"]}_{person_index}'
            )
            
            person_to_intervals[person_index].append(optional_interval)

    # Add the NoOverlap constraint for each person (resource)
    for person_intervals in person_to_intervals:
        model.AddNoOverlap(person_intervals)


    # --- 3. Objective Function: Minimize Total UAT Time ---
    
    # Find the maximum end time across all shared scenario end variables
    all_end_vars = list(set([subtask['end'] for subtask in all_subtasks]))
    
    max_end_time = model.NewIntVar(0, horizon, 'max_end_time')
    model.AddMaxEquality(max_end_time, all_end_vars)
    
    model.Minimize(max_end_time)
    
    # --- 4. Solve and Format Output ---
    
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Re-group the results by the original scenario name
        scenario_results = {}
        
        for subtask in all_subtasks:
            scenario_name = subtask['scenario_name']
            
            # Get solved values (all subtasks of a scenario will have the same start/end time)
            start_hour_offset = solver.Value(subtask['start'])
            end_hour_offset = solver.Value(subtask['end'])
            person_index = solver.Value(subtask['person'])
            
            assigned_person = personnel[person_index]['name']
            assigned_workstream = personnel[person_index]['workstream']
            
            if scenario_name not in scenario_results:
                start_dt = start_date + timedelta(hours=start_hour_offset)
                end_dt = start_date + timedelta(hours=end_hour_offset)
                
                scenario_results[scenario_name] = {
                    'Scenario': scenario_name,
                    'Duration (Hours)': subtask['duration'],
                    'Start Time': start_dt.strftime('%Y-%m-%d %H:%M'),
                    'End Time': end_dt.strftime('%Y-%m-%d %H:%M'),
                    'Assigned Persons': [],
                    'Workstreams': []
                }
            
            scenario_results[scenario_name]['Assigned Persons'].append(assigned_person)
            scenario_results[scenario_name]['Workstreams'].append(assigned_workstream)

        final_results = []
        for res in scenario_results.values():
            # Format the output lists for display
            res['Assigned Persons'] = ", ".join(sorted(res['Assigned Persons']))
            res['Workstreams'] = ", ".join(sorted(res['Workstreams']))
            final_results.append(res)
            
        return pd.DataFrame(final_results), solver.ObjectiveValue() / 24.0
    
    return pd.DataFrame(), None