import hvplot.pandas
import panel as pn
import param
import numpy as np
import pandas as pd
import holoviews as hv
from holoviews import opts
import networkx as nx
from ABM_simulation.model import CirclesNetwork
from ABM_simulation.agents import HumanAgent, HubAgent
from ABM_simulation.logger import get_logger
import logging

hvplot.extension('bokeh')

class SimulationDashboard(param.Parameterized):
    update_frequency = param.Integer(default=10)
    current_step = param.Integer(default=0)
    max_steps = param.Integer(default=0)
    is_running = param.Boolean(default=False)
    metrics_df = param.DataFrame(default=pd.DataFrame())
    mint_df = param.DataFrame(default=pd.DataFrame())
    simulation_complete = param.Boolean(default=False)
    activation_fraction = param.Number(default=0.1, bounds=(0.01, 1))

    log_level = param.ObjectSelector(default='INFO', objects=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])

    def __init__(self, **params):
        super().__init__(**params)
        self.model = None
        self.logger = None
        self.update_logger()
        self.cumulative_mint_count = 0
        self.cumulative_mint_value = 0

    @param.depends('log_level', watch=True)
    def update_logger(self):
        self.logger = get_logger("SimulationDashboard", getattr(logging, self.log_level))

    def run_model(self, steps, update_freq):
        self.model = CirclesNetwork(initial_agents=5, activation_fraction=self.activation_fraction, log_level=self.log_level)
        self.logger.info(f"Initial agents: {len([a for a in self.model.schedule.agents if isinstance(a, HumanAgent)])}")
        self.logger.info(f"Initial graph nodes: {self.model.G.number_of_nodes()}")
        self.current_step = 0
        self.max_steps = steps
        self.update_frequency = update_freq
        self.metrics_df = pd.DataFrame()
        self.mint_df = pd.DataFrame()
        self.is_running = True
        self.simulation_complete = False

    def step_model(self):
        if self.current_step < self.max_steps and self.is_running:
            try:
                self.model.step()
                self.current_step += 1
                
                # Collect mint data at every step
                new_mint_data = self.calculate_mint_metrics()
                new_mint_df = pd.DataFrame([new_mint_data])
                self.mint_df = pd.concat([self.mint_df, new_mint_df], ignore_index=True)
                
                if self.current_step % self.update_frequency == 0 or self.current_step == self.max_steps:
                    human_agents_count = len([a for a in self.model.schedule.agents if isinstance(a, HumanAgent)])
                    self.logger.info(f"Dashboard Step {self.current_step}: Human Agents: {human_agents_count}, Nodes: {self.model.G.number_of_nodes()}, Edges: {self.model.G.number_of_edges()}")
                    
                    new_metrics = self.calculate_graph_metrics()
                    new_df = pd.DataFrame([new_metrics])
                    self.metrics_df = pd.concat([self.metrics_df, new_df], ignore_index=True)
                    
                    if self.current_step >= self.max_steps:
                        self.is_running = False
                        self.simulation_complete = True
                    
                    return True  # Indicate an update is needed
                return False  # Indicate no update is needed
            except Exception as e:
                self.logger.error(f"Error during model step: {str(e)}")
                self.is_running = False
                return True
        return False


    def create_network_graph(self):
        if self.model is None or self.model.G.number_of_nodes() == 0:
            return hv.Text(0, 0, "No nodes in the graph yet").opts(responsive=True, aspect=1)
        
        # Create a copy of the graph with string node identifiers
        G_str = nx.relabel_nodes(self.model.G, {n: str(n) for n in self.model.G.nodes()})
        
        # Create the layout with string node identifiers
        layout = nx.spring_layout(G_str)
        
        return hv.Graph.from_networkx(G_str, layout).opts(
            directed=True, arrowhead_length=0.002,
            responsive=True, aspect=1, tools=['hover'], active_tools=[], node_size=4, edge_line_width=0.5
        )

    def create_adjacency_matrix(self):
        if self.model is None or self.model.G.number_of_nodes() == 0:
            return hv.Image(np.array([[0]])).opts(responsive=True, aspect=1, cmap='viridis', title="No nodes in the graph yet")
        return hv.Image(nx.adjacency_matrix(self.model.G).todense()).opts(
            responsive=True, aspect=1, cmap='viridis', tools=['hover'], active_tools=[]
        )

    def calculate_graph_metrics(self):
        if self.model is None:
            return {'Nodes': 0, 'Edges': 0, 'Avg Degree': 0, 'Density': 0, 'Activated Agents': 0, 'Total Human Agents': 0}
        graph = self.model.G
        num_nodes = graph.number_of_nodes()
        num_edges = graph.number_of_edges()
        avg_degree = np.mean([d for n, d in graph.degree()]) if num_nodes > 0 else 0
        density = nx.density(graph) if num_nodes > 1 else 0
        human_agents_count = len([a for a in self.model.schedule.agents if isinstance(a, HumanAgent)])
        return {
            'Nodes': num_nodes,
            'Edges': num_edges,
            'Avg Degree': avg_degree,
            'Density': density,
            'Activated Agents': self.model.activated_agents_count,
            'Total Human Agents': human_agents_count
        }


    def calculate_mint_metrics(self):
        new_mint_count = 0
        new_mint_value = 0
        for agent in self.model.schedule.agents:
            if isinstance(agent, HumanAgent):
                mints = self.model.hub_agent.get_mints(agent.unique_id)
                for step, mint_info in mints.items():
                    if step == self.current_step:
                        new_mint_count += 1
                        new_mint_value += mint_info['issuance']
        
        self.cumulative_mint_count += new_mint_count
        self.cumulative_mint_value += new_mint_value
        
        # Convert the mint value to a more manageable unit (e.g., standard tokens)
        new_mint_value_standard = new_mint_value / 1e18
        cumulative_mint_value_standard = self.cumulative_mint_value / 1e18

        metrics = {
            'Step': self.current_step,
            'New Mint Count': new_mint_count,
            'New Mint Value': new_mint_value_standard,
            'Cumulative Mint Count': self.cumulative_mint_count,
            'Cumulative Mint Value': cumulative_mint_value_standard
        }
        
        self.logger.debug(f"Mint metrics for step {self.current_step}: {metrics}")
        
        return metrics

    def create_mint_plot(self):
        self.logger.debug(f"Creating mint plot. mint_df shape: {self.mint_df.shape}")
        if self.mint_df.empty:
            self.logger.warning("Mint DataFrame is empty")
            return (hv.Text(0, 0, "No mint data yet").opts(responsive=True, aspect=1),
                    hv.Text(0, 0, "No mint data yet").opts(responsive=True, aspect=1))
        
        self.logger.debug(f"Mint DataFrame:\n{self.mint_df}")
        
        try:
            # Mint Count Plot
            new_mint_count = hv.Bars(self.mint_df, 'Step', 'New Mint Count').opts(
                color='blue', alpha=0.6, ylabel='New Mint Count',
               tools=['hover'], active_tools=[]
            )
            cumulative_mint_count = hv.Curve(self.mint_df, 'Step', 'Cumulative Mint Count').opts(
                color='red', ylabel='Cumulative Mint Count'
            )
            
            count_plot = (new_mint_count * cumulative_mint_count).opts(
                opts.Overlay(responsive=True, aspect=1,
                            xlabel='Step', legend_position='top_left',
                            show_grid=True, multi_y=True),

            ).opts(responsive=True, aspect=1, tools=['hover'], active_tools=[])

            # Mint Value Plot
            new_mint_value = hv.Bars(self.mint_df, 'Step', 'New Mint Value').opts(
                color='green', alpha=0.6, ylabel='New Mint Value',
                tools=['hover'], active_tools=[]
            )
            cumulative_mint_value = hv.Curve(self.mint_df, 'Step', 'Cumulative Mint Value').opts(
                color='orange', ylabel='Cumulative Mint Value'
            )
            
            value_plot = (new_mint_value * cumulative_mint_value).opts(
                opts.Overlay(width=500, height=350,
                            xlabel='Step', legend_position='top_left',
                            show_grid=True, multi_y=True),
            ).opts(width=500, height=350, tools=['hover'], active_tools=[])

            self.logger.debug("Dual-axis mint plots created successfully")
            return count_plot, value_plot
        except Exception as e:
            self.logger.error(f"Error creating mint plots: {str(e)}", exc_info=True)
            return (hv.Text(0, 0, f"Error: {str(e)}").opts(width=500, height=350),
                    hv.Text(0, 0, f"Error: {str(e)}").opts(width=500, height=350))
        
dashboard = SimulationDashboard()

# Create widgets
steps_slider = pn.widgets.IntSlider(name="Steps", start=1, end=300, value=100)
fred_slider = pn.widgets.IntSlider(name="Update Frequency", start=1, end=300, value=10)
activation_fraction_slider = pn.widgets.FloatSlider(name="Fraction of Agents Activated per Step", start=0.01, end=1.0, value=0.1, step=0.01)
run_button = pn.widgets.Button(name="Run Simulation", button_type="primary")
stop_button = pn.widgets.Button(name="Stop", button_type="danger")
continue_button = pn.widgets.Button(name="Continue", button_type="success")
real_time_toggle = pn.widgets.Checkbox(name="Update plots in real-time", value=True)
progress = pn.indicators.Progress(name="Progress", value=0, width=200)
log_level_select = pn.widgets.Select(name="Log Level", options=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], value='INFO')


def update_plots():
    dashboard.logger.debug(f"Updating plots. Current step: {dashboard.current_step}")
    network_graph_pane.object = dashboard.create_network_graph()
    adjacency_matrix_pane.object = dashboard.create_adjacency_matrix()
    
    if not dashboard.metrics_df.empty:
        metrics_df_melted = dashboard.metrics_df.reset_index().melt(id_vars=['index'], var_name='Metric', value_name='Value')
        metrics_plot = metrics_df_melted.hvplot.line(
            x='index', y='Value', by='Metric', responsive=True, aspect=1
        ).opts(tools=['hover'], active_tools=[], legend_position='top')
        metrics_plot_pane.object = metrics_plot
    else:
        metrics_plot_pane.object = hv.Text(0, 0, "No metrics data yet").opts(width=1250, height=300)
    
    mint_count_plot, mint_value_plot = dashboard.create_mint_plot()
    mint_count_plot_pane.object = mint_count_plot
    mint_value_plot_pane.object = mint_value_plot
    dashboard.logger.debug("Plots updated successfully")

def update_simulation():
    update_needed = False
    while not update_needed and dashboard.is_running:
        update_needed = dashboard.step_model()
    
    if update_needed:
        progress.value = int((dashboard.current_step / dashboard.max_steps) * 100)

        if real_time_toggle.value:
            update_plots()
        if dashboard.simulation_complete:
            periodic_callback.stop()
            update_plots()
            dashboard.logger.info("Simulation completed")

def run_simulation(event):
    dashboard.logger.info("Starting new simulation")
    dashboard.run_model(steps_slider.value, fred_slider.value)
    progress.value = 0
    update_plots()  # Initial plot
    if not periodic_callback.running:
        periodic_callback.start()

def stop_simulation(event):
    dashboard.logger.info("Stopping simulation")
    dashboard.is_running = False
    if periodic_callback.running:
        periodic_callback.stop()
    update_plots()  # Update plots with final state when stopped

def continue_simulation(event):
    if dashboard.model is not None and not dashboard.is_running:
        dashboard.logger.info("Continuing simulation")
        dashboard.is_running = True
        if not periodic_callback.running:
            periodic_callback.start()

def update_log_level(event):
    dashboard.log_level = event.new
    dashboard.update_logger()
    dashboard.logger.info(f"Log level changed to {event.new}")

def update_activation_fraction(event):
    dashboard.activation_fraction = event.new
    dashboard.logger.info(f"Fraction of agents activated per step changed to {event.new}")

run_button.on_click(run_simulation)
stop_button.on_click(stop_simulation)
continue_button.on_click(continue_simulation)
log_level_select.param.watch(update_log_level, 'value')
activation_fraction_slider.param.watch(update_activation_fraction, 'value')

# Create periodic callback
periodic_callback = pn.state.add_periodic_callback(update_simulation, period=100)
periodic_callback.stop()

# Create the layout
template = pn.template.ReactTemplate(title='Circles UBI Network Simulation Playground')

# Add widgets to sidebar
template.sidebar.extend([
    steps_slider,
    fred_slider,
    activation_fraction_slider,
    pn.Row(run_button, stop_button, continue_button, width=250),
    real_time_toggle,
    log_level_select,
    progress
])

network_graph_pane = pn.pane.HoloViews(sizing_mode='stretch_both')
adjacency_matrix_pane = pn.pane.HoloViews(sizing_mode='stretch_both')
metrics_plot_pane = pn.pane.HoloViews(sizing_mode='stretch_both')
mint_count_plot_pane = pn.pane.HoloViews(sizing_mode='stretch_both')
mint_value_plot_pane = pn.pane.HoloViews(sizing_mode='stretch_both')
empty_content = pn.Column(sizing_mode='stretch_both')

# Add plots to the main area using GridSpec indexing
template.main[0:3, 0:5] = pn.Card(network_graph_pane, title='Network Graph', sizing_mode='stretch_both')
template.main[0:3, 5:10] = pn.Card(adjacency_matrix_pane, title='Adjacency Matrix', sizing_mode='stretch_both')
template.main[3:6, :] = pn.Card(metrics_plot_pane, title='Graph Metrics Over Time', sizing_mode='stretch_both')
template.main[6:9, 0:5] = pn.Card(mint_count_plot_pane, title='Mint Count Over Time', sizing_mode='stretch_both')
template.main[6:9, 5:10] = pn.Card(mint_value_plot_pane, title='Mint Value Over Time', sizing_mode='stretch_both')
template.main[9:10, :] = empty_content



# Serve the template
pn.serve(template)