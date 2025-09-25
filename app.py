# app.py - THE INTERACTIVE USER INTERFACE

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from solver import find_optimal_schedule 
import ast # Need this for safely turning that string input back into a Python list!

st.set_page_config(layout="wide", page_title="UAT Scheduling Optimizer")

def app():
    st.title("Scheduling Optimizer")
    st.markdown("This tool uses CSP to find the **best possible multi-resource schedule** for your cross-workstream UAT!")

    # --- 1. Let's Get Your Data In Here! ---
    st.header("1. UAT Setup & Data Input")
    
    # First, when does this whole thing kick off?
    start_date = st.date_input("Select UAT Start Date", datetime.now())
    start_date_str = start_date.strftime('%Y-%m-%d')
    
    # Using tabs keeps the interface nice and tidy.
    tab1, tab2 = st.tabs(["Personnel (Resources)", "UAT Scenarios (Tasks)"])
    
    # Just providing some starter data, so folks don't have to start from scratch.
    default_personnel_data = [
        {'name': 'Alice', 'workstream': 'Finance'},
        {'name': 'Bob', 'workstream': 'Logistics'},
        {'name': 'Charlie', 'workstream': 'IT'},
    ]
    # Note: We keep the workstreams here as a string that LOOKS like a list for the editor.
    default_scenario_data = [
        {'name': 'P2P End-to-End', 'duration_hours': 12, 'required_workstreams': "['Finance', 'Logistics', 'IT']"},
        {'name': 'Invoice Posting', 'duration_hours': 6, 'required_workstreams': "['Finance']"},
    ]


    # --- TAB 1: PERSONNEL DATA INPUT ---
    with tab1:
        st.subheader("Edit Personnel and Workstreams")
        st.caption(" who's available and what team they're on")
        
        # The data editor is so handy for this!
        personnel_df = st.data_editor(
            pd.DataFrame(default_personnel_data),
            num_rows="dynamic",
            width='stretch' ,
            key='personnel_editor'
        )
        # Convert it back to the format the solver likes.
        personnel_data = personnel_df.to_dict('records')


    # --- TAB 2: SCENARIO DATA INPUT ---
    with tab2:
        st.subheader("Edit UAT Scenarios and Requirements")
        st.info("**Important** Please enter **Required Workstreams** exactly like this in array format: `['Finance', 'IT']`.")

        scenario_df = st.data_editor(
            pd.DataFrame(default_scenario_data),
            num_rows="dynamic",
            width='stretch' ,
            key='scenario_editor'
        )
        
        # We need some special handling to clean up the user's list input.
        scenario_data = []
        for index, row in scenario_df.iterrows():
            try:
                # Safely converting the user's string input back to a Python list.
                ws_list = ast.literal_eval(str(row['required_workstreams'])) 
                if not isinstance(ws_list, list):
                    ws_list = [str(row['required_workstreams'])]
            except (ValueError, SyntaxError):
                ws_list = [] # If they mess up the format, it's okay, we'll just skip it.
            
            scenario_data.append({
                'name': str(row['name']),
                'duration_hours': row['duration_hours'],
                'required_workstreams': ws_list
            })
    
    
    # --- 2. Time to Crunch the Numbers! ---
    st.header("2. Generate Schedule")

    if st.button("🚀 Find Optimal Schedule"):
        # Quick validation check, wouldn't want to run on empty data!
        if not personnel_data or not scenario_data or len(personnel_data) == 0 or len(scenario_data) == 0:
            st.error("Oops! Please make sure both Personnel and Scenario tables have data before running.")
            return

        with st.spinner("Solving some really tough resource allocation problems"):
            
            # Sending the data off to our smart solver function.
            schedule_df, total_days = find_optimal_schedule(scenario_data, personnel_data, start_date_str)
            
            if schedule_df is None or schedule_df.empty:
                 st.error(" The solver couldn't find a way to make it work. Check if every required workstream has at least one person available.")
                 return

            st.success("Optimization Complete! We found the best schedule.")

            # --- 3. Check Out the Results! ---
            st.header("3. optimal UAT Schedule")
            
            # Key metric up front!
            st.metric("Total UAT Duration ", f"{total_days:.1f} Days")

            # Data Table
            st.subheader("scheduled Details")
            st.dataframe(schedule_df, width='stretch' )

            # --- Gantt Chart Visualization ---
            st.subheader("gantt chart visualization")
            
            # Prepping the data for the visual.
            schedule_df['Start_DT'] = pd.to_datetime(schedule_df['Start Time'])
            schedule_df['Finish_DT'] = pd.to_datetime(schedule_df['End Time'])
            
            # This is the final visual: Scenario is on the Y-axis, and we'll use the hover text to show who's assigned!
            fig = px.timeline(
                schedule_df,
                x_start="Start_DT", 
                x_end="Finish_DT", 
                y="Scenario",
                color="Workstreams",
                hover_name="Scenario",
                # Including the key details in the tooltip.
                hover_data=['Assigned Persons', 'Workstreams', 'Duration (Hours)', 'Start Time', 'End Time'], 
                title="UAT Scenario Timeline by Resource Allocation"
            )
            fig.update_yaxes(autorange="reversed") 
            st.plotly_chart(fig, width='stretch' )

if __name__ == '__main__':
    app()