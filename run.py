import yaml
import argparse
from datetime import datetime
import os
import pandas as pd
import numpy as np
import networkx as nx
import json
from ABM_simulation.model import CirclesNetwork
from ABM_simulation.logger import get_logger
import logging

def load_config(config_file):
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def run_simulation(config, run_number):
    logger = get_logger(f"SimulationRunner_Run{run_number}", getattr(logging, config.get('log_level', 'INFO')))
    logger.info(f"Starting simulation run {run_number} with configuration:")
    logger.info(config)

    model = CirclesNetwork(
        initial_agents=config.get('initial_agents', 5),
        activation_fraction=config.get('activation_fraction', 0.1),
        log_level=config.get('log_level', 'INFO')
    )

    steps = config.get('steps', 100)
    
    graph_data = []
    for i in range(steps):
        model.step()
        graph_data.append(nx.node_link_data(model.G))
        if (i + 1) % 10 == 0:
            logger.info(f"Completed step {i + 1}")

    model_data = model.datacollector.get_model_vars_dataframe()
    agent_data = model.datacollector.get_agent_vars_dataframe()
    
    return model_data, agent_data, graph_data

def save_data(model_data, agent_data, graph_data, config, run_number, timestamp):
    output_dir = config.get('output_dir', 'data')
    os.makedirs(output_dir, exist_ok=True)
    
    base_filename = config.get('output_filename', 'simulation_results')
    
    # Save model-level data
    model_filename = f"{base_filename}_model_run{run_number}_{timestamp}.csv"
    model_full_path = os.path.join(output_dir, model_filename)
    model_data.to_csv(model_full_path, index=True)
    print(f"Model data for run {run_number} saved to {model_full_path}")
    
    # Save agent-level data
    agent_filename = f"{base_filename}_agents_run{run_number}_{timestamp}.csv"
    agent_full_path = os.path.join(output_dir, agent_filename)
    agent_data.to_csv(agent_full_path, index=True)
    print(f"Agent data for run {run_number} saved to {agent_full_path}")

    # Save graph data
    graph_filename = f"{base_filename}_graph_run{run_number}_{timestamp}.json"
    graph_full_path = os.path.join(output_dir, graph_filename)
    with open(graph_full_path, 'w') as f:
        json.dump(graph_data, f)
    print(f"Graph data for run {run_number} saved to {graph_full_path}")

def run_multiple_simulations(config):
    num_runs = config.get('num_runs', 1)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    all_model_data = []
    all_agent_data = []
    
    for run in range(1, num_runs + 1):
        model_data, agent_data, graph_data = run_simulation(config, run)
        save_data(model_data, agent_data, graph_data, config, run, timestamp)
        
        # Convert Network data to number of nodes and edges
        if 'Network' in model_data.columns:
            model_data['Num_Nodes'] = model_data['Network'].apply(lambda g: len(g['nodes']))
            model_data['Num_Edges'] = model_data['Network'].apply(lambda g: len(g['links']))
            model_data = model_data.drop('Network', axis=1)
        
        all_model_data.append(model_data)
        all_agent_data.append(agent_data)
    
    # Combine data from all runs
    combined_model_data = pd.concat(all_model_data, keys=range(1, num_runs + 1))
    
    # Calculate summary statistics for numeric columns only
    numeric_columns = combined_model_data.select_dtypes(include=[np.number]).columns
    mean_model_data = combined_model_data[numeric_columns].groupby(level=1).mean()
    std_model_data = combined_model_data[numeric_columns].groupby(level=1).std()
    
    # Save summary statistics
    summary_filename = f"{config.get('output_filename', 'simulation_results')}_summary_{timestamp}.csv"
    summary_full_path = os.path.join(config.get('output_dir', 'data'), summary_filename)
    summary_data = pd.concat([mean_model_data, std_model_data], axis=1, keys=['mean', 'std'])
    summary_data.to_csv(summary_full_path)
    print(f"Summary statistics saved to {summary_full_path}")

def main():
    parser = argparse.ArgumentParser(description="Run Circles UBI simulation from YAML config")
    parser.add_argument('config', help="Path to YAML configuration file")
    args = parser.parse_args()

    config = load_config(args.config)
    run_multiple_simulations(config)

if __name__ == "__main__":
    main()