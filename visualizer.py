import panel as pn
import param
import pandas as pd
import holoviews as hv
from holoviews import opts
import networkx as nx
import json
import os
from pathlib import Path
import logging
import hvplot.pandas

pn.extension('tabulator')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SimulationVisualizer(param.Parameterized):
    simulation_dir = param.String(default='data')
    selected_simulation = param.ObjectSelector(default=None, objects=[])
    run_options = param.List([])
    selected_run = param.Integer(default=None)
    view = param.Parameter()

    def __init__(self, **params):
        super().__init__(**params)
        self.main_pane = pn.pane.Markdown("Select a simulation to view.")
        self.simulations = {}
        self.summary_data = None
        self.run_data = None
        self.param.selected_simulation.objects = ["Loading..."]
        self.selected_simulation = "Loading..."
        self.load_simulations()

    @param.depends('selected_simulation', 'selected_run')
    def view(self):
        if not self.selected_simulation or self.selected_simulation == "Loading...":
            return pn.pane.Markdown("Please select a simulation to view.")
        
        summary_plot = self.create_summary_plot()
        run_plots = self.create_run_plots()
        
        return pn.Column(
            summary_plot,
            pn.Spacer(height=20),
            pn.Row(
                run_plots['network_graph'],
                pn.Spacer(width=20),
                run_plots['adjacency_matrix'],
                sizing_mode='stretch_width'
            ),
            pn.Spacer(height=20),
            run_plots['metrics'],
            pn.Spacer(height=20),
            pn.Row(
                run_plots['mint_count'],
                pn.Spacer(width=20),
                run_plots['mint_value'],
                sizing_mode='stretch_width'
            ),
            pn.Spacer(height=20),
            pn.Row(
                run_plots['transaction_count'],
                pn.Spacer(width=20),
                run_plots['transaction_value'],
                sizing_mode='stretch_width'
            ),
            pn.Spacer(height=20),
            run_plots['agent_scatter'],
            pn.Spacer(height=20),
            pn.Row(pn.Spacer(height=200), sizing_mode='stretch_width'),
            sizing_mode='stretch_width'
        )
        
    def load_simulations(self):
        logger.debug("Loading simulations...")
        self.simulations = {}
        try:
            script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            data_dir = script_dir / self.simulation_dir
            logger.debug(f"Looking for simulations in: {data_dir}")
            
            if not data_dir.exists():
                logger.error(f"Data directory does not exist: {data_dir}")
                raise FileNotFoundError(f"Data directory not found: {data_dir}")
            
            summary_files = list(data_dir.glob('*_summary_*.csv'))
            logger.debug(f"Found {len(summary_files)} summary files")
            
            for summary_file in summary_files:
                parts = summary_file.stem.split('_')
                sim_name = '_'.join(parts[:-3])  
                timestamp = '_'.join(parts[-2:])
                sim_key = f"{sim_name}_{timestamp}"
                
                self.simulations[sim_key] = {
                    'timestamp': timestamp,
                    'runs': set(),
                    'model_files': {},
                    'agents_files': {},
                    'graph_files': {}
                }
                
                for file_type in ['model', 'agents', 'graph']:
                    files = list(data_dir.glob(f'{sim_name}_{file_type}_run*_{timestamp}.*'))
                    for file in files:
                        run_parts = file.stem.split('_')
                        run_number = int(run_parts[-3][3:])
                        self.simulations[sim_key]['runs'].add(run_number)
                        self.simulations[sim_key][f'{file_type}_files'][run_number] = str(file)
                
                logger.debug(f"Parsed simulation: {sim_key} with {len(self.simulations[sim_key]['runs'])} runs")
            
            logger.debug(f"Parsed simulations: {self.simulations}")
            
            sim_options = []
            for sim_key, sim_data in self.simulations.items():
                if sim_data['runs']:
                    run_count = len(sim_data['runs'])
                    sim_options.append(f"{sim_key} ({run_count} runs)")
    
            logger.debug(f"Found {len(sim_options)} valid simulations")
            if sim_options:
                self.param.selected_simulation.objects = sim_options
                self.selected_simulation = sim_options[0]
                self.load_summary_data()
            else:
                logger.warning("No valid simulations found in the specified directory.")
                self.param.selected_simulation.objects = [("No simulations found", None)]
        except Exception as e:
            logger.error(f"Error loading simulations: {str(e)}")
            self.param.selected_simulation.objects = [("Error loading simulations", None)]

    @param.depends('selected_simulation', watch=True)
    def _update_on_simulation_change(self):
        logger.debug(f"Simulation changed to: {self.selected_simulation}")
        if self.selected_simulation != "Loading...":
            self.load_summary_data()
            self.update_run_options()

    def load_summary_data(self):
        if self.selected_simulation != "Loading...":
            sim_key = self.selected_simulation.split(' (')[0]
            sim_name = '_'.join(sim_key.split('_')[:-2])
            summary_file = next(Path(self.simulation_dir).glob(f"{sim_name}_summary_*.csv"))
            
            self.summary_data = pd.read_csv(summary_file)

            # Convert all columns except 'Step' to float
            for column in self.summary_data.columns:
                if column != 'Step':
                    self.summary_data[column] = pd.to_numeric(self.summary_data[column], errors='coerce')
            
            # Convert 'Step' to integer (assuming it's a step or index column)
            self.summary_data['Step'] = pd.to_numeric(self.summary_data['Step'], errors='coerce').astype('Int64')
            
            logger.debug(f"Loaded summary data with columns: {self.summary_data.columns}")

    def update_run_options(self):
        if self.selected_simulation != "Loading...":
            sim_key = self.selected_simulation.split(' (')[0]
            new_run_options = sorted(list(self.simulations[sim_key]['runs']))
            logger.debug(f"Updated run options: {new_run_options}")
            self.run_options = new_run_options
            if new_run_options:
                self.selected_run = new_run_options[0]
            else:
                self.selected_run = None
            self.param.trigger('run_options')
            self.load_run_data()  # Load data for the first run

    @param.depends('selected_run', watch=True)
    def load_run_data(self):
        if self.selected_simulation != "Loading..." and self.selected_run is not None:
            sim_key = self.selected_simulation.split(' (')[0]
            run_data = self.simulations[sim_key]
            
            if self.selected_run not in run_data['model_files']:
                logger.error(f"Selected run {self.selected_run} does not exist")
                self.run_data = None
                return

            model_file = run_data['model_files'][self.selected_run]
            agent_file = run_data['agents_files'][self.selected_run]
            graph_file = run_data['graph_files'][self.selected_run]
            
            self.run_data = {
                'model': pd.read_csv(model_file),
                'agent': pd.read_csv(agent_file),
                'graph': json.load(open(graph_file, 'r'))
            }

            # Add AgentID column to agent data if it doesn't exist
            if 'AgentID' not in self.run_data['agent'].columns:
                self.run_data['agent']['AgentID'] = self.run_data['agent'].groupby('Step').cumcount()
            
            
            logger.debug(f"Loaded run data for run {self.selected_run}")
    
    def create_summary_plot(self):
        if self.summary_data is None:
            logger.error("Summary data not loaded")
            return pn.pane.Markdown("No summary data available.")

        mean_columns = [col for col in self.summary_data.columns if col.endswith('_mean')]

        if not mean_columns:
            logger.warning("No mean columns found in summary data")
            return pn.pane.Markdown("No relevant data found in the summary.")

        plot = self.summary_data.hvplot.line(
            x='Step', y=mean_columns,
            width=None,
            height=400,
            responsive=True,
            legend='top'
        ).opts(
            tools=['hover'],
            active_tools=[],
            fontscale=1,
            ylim=(0, None) 
        )
        return pn.Card(
            pn.pane.HoloViews(plot, sizing_mode='stretch_width', height=450),
            title=f"Summary (Run: {self.selected_run})",
            sizing_mode='stretch_width'
        )

    def process_data(self, data_type, columns):
        """
        Generic method to process data for visualization.
        
        :param data_type: Type of data (e.g., 'mint', 'transaction')
        :param columns: List of column names [step, cumulative_count, cumulative_value]
        :return: Processed DataFrame
        """
        if 'model' not in self.run_data or self.run_data['model'] is None:
            logger.error(f"{data_type.capitalize()} data not found in run_data")
            return pd.DataFrame()

        step, cumulative_count, cumulative_value = columns
        data = self.run_data['model'][[step, cumulative_count, cumulative_value]].copy()
        data.columns = ['Step', f'Cumulative {data_type.capitalize()} Count', f'Cumulative {data_type.capitalize()} Value']

        # Convert columns to numeric, replacing any non-numeric values with NaN
        for col in data.columns[1:]:
            data[col] = pd.to_numeric(data[col], errors='coerce')

        # Calculate the differences and fill NaN with 0
        data[f'New {data_type.capitalize()} Count'] = data[f'Cumulative {data_type.capitalize()} Count'].diff().fillna(data[f'Cumulative {data_type.capitalize()} Count'])
        data[f'New {data_type.capitalize()} Value'] = data[f'Cumulative {data_type.capitalize()} Value'].diff().fillna(data[f'Cumulative {data_type.capitalize()} Value'])

        return data

    def process_mint_data(self):
        return self.process_data('mint', ['Step', 'TotalMints', 'TotalMintVolume'])

    def process_transaction_data(self):
        return self.process_data('transaction', ['Step', 'TotalTransactions', 'TotalTransactionVolume'])


    def create_run_plots(self):
        if self.run_data is None:
            logger.error("Run data not loaded")
            return {"error": pn.pane.Markdown("No run data available.")}

        plots = {}
        
        # Network Graph and Adjacency Matrix
        plots['network_graph'] = self.create_single_plot('network_graph', self.create_network_graph, "Network Graph")
        plots['adjacency_matrix'] = self.create_single_plot('adjacency_matrix', self.create_adjacency_matrix, "Adjacency Matrix")
        
        # Metrics Plot
        plots['metrics'] = self.create_single_plot('metrics', self.create_metrics_plot, "Model Metrics")
        
        # Mint Plots
        mint_data = self.process_mint_data()
        plots['mint_count'] = self.create_dual_axis_plot('mint_count', mint_data, 'New Mint Count', 'Cumulative Mint Count', "Mint Count")
        plots['mint_value'] = self.create_dual_axis_plot('mint_value', mint_data, 'New Mint Value', 'Cumulative Mint Value', "Mint Value")
        
        # Transaction Plots
        transaction_data = self.process_transaction_data()
        plots['transaction_count'] = self.create_dual_axis_plot('transaction_count', transaction_data, 'New Transaction Count', 'Cumulative Transaction Count', "Transaction Count")
        plots['transaction_value'] = self.create_dual_axis_plot('transaction_value', transaction_data, 'New Transaction Value', 'Cumulative Transaction Value', "Transaction Value")
        
        # Agent Scatter Plot
        plots['agent_scatter'] = self.create_single_plot('agent_scatter', self.create_agent_scatter_plot, "Agent Balance vs Supply")

        return plots

    def create_single_plot(self, plot_name, plot_function, title):
        try:
            plot = plot_function()
            return pn.Card(
                pn.pane.HoloViews(plot, sizing_mode='stretch_width', height=400),
                title=f"{title} (Run: {self.selected_run})",
                sizing_mode='stretch_width'
            )
        except Exception as e:
            logger.error(f"Error creating {plot_name}: {str(e)}")
            return pn.pane.Markdown(f"Error creating {plot_name}: {str(e)}")

    def create_dual_axis_plot(self, plot_name, data, bar_column, line_column, title):
        try:
            bar_plot = data.hvplot.bar(
                x='Step', y=bar_column, color='blue', alpha=0.6
            ).opts(ylabel=bar_column, tools=['hover'], active_tools=[])
            
            line_plot = data.hvplot.line(
                x='Step', y=line_column, color='red'
            ).opts(ylabel=line_column)
            
            combined_plot = (bar_plot * line_plot).opts(
                opts.Overlay(responsive=True, aspect=1, xlabel='Step', 
                             legend_position='top_left', show_grid=True, multi_y=True)
            )
            
            return pn.Card(
                pn.pane.HoloViews(combined_plot, sizing_mode='stretch_width', height=400),
                title=f"{title} (Run: {self.selected_run})",
                sizing_mode='stretch_width'
            )
        except Exception as e:
            logger.error(f"Error creating {plot_name}: {str(e)}")
            return pn.pane.Markdown(f"Error creating {plot_name}: {str(e)}")

    def create_network_graph(self):
        last_graph = nx.node_link_graph(self.run_data['graph'][-1])
        last_graph = nx.relabel_nodes(last_graph, {n: str(n) for n in last_graph.nodes()})
        layout = nx.spring_layout(last_graph)
        return hv.Graph.from_networkx(last_graph, layout).opts(
            width=None, height=400, tools=['hover'], active_tools=[],
            node_size=10, edge_line_width=0.5, xaxis=None, yaxis=None,
            responsive=True
        )

    def create_adjacency_matrix(self):
        last_graph = nx.node_link_graph(self.run_data['graph'][-1])
        adjacency_matrix = nx.adjacency_matrix(last_graph).todense()
        return hv.Image(adjacency_matrix).opts(
            width=None, height=400, cmap='viridis',
            tools=['hover'], active_tools=[], colorbar=True,
            responsive=True
        )

    def create_metrics_plot(self):
        model_columns = [col for col in self.run_data['model'].columns if col not in ['Step', 'Network']]
        return self.run_data['model'].hvplot.line(
            x='Step', y=model_columns, width=None, height=350,
            legend='top'
        ).opts(
            tools=['hover'], active_tools=[], fontscale=1, ylim=(0, None)
        )

    def create_agent_scatter_plot(self):
        return self.run_data['agent'].hvplot.scatter(
            x='Balance', y='Supply', by='AgentID', width=800, height=400,
            title="Agent Balance vs Supply"
        ).opts(tools=['hover'], active_tools=['pan', 'wheel_zoom'])

# Create the Panel application
visualizer = SimulationVisualizer()

simulation_select = pn.widgets.Select(
    name='Select Simulation',
    options=visualizer.param.selected_simulation.objects,
    value=visualizer.selected_simulation,
    width=300
)

run_select = pn.widgets.Select(
    name='Select Run',
    options=visualizer.param.run_options,
    value=visualizer.param.selected_run,
    width=300
)

# Create the layout
template = pn.template.ReactTemplate(
    title='Circles UBI Simulation Visualizer'
)

# Add widgets to sidebar
template.sidebar.extend([
    #pn.pane.Markdown("## Controls", style={'font-weight': 'bold'}),
    simulation_select,
    run_select
])

# Bind the widgets to the visualizer parameters
def update_run_select(event):
    run_select.options = event.new
    run_select.value = visualizer.selected_run

visualizer.param.watch(update_run_select, 'run_options')
simulation_select.link(visualizer, value='selected_simulation')
run_select.link(visualizer, value='selected_run')

# Assign the content to the main area
template.main[:, :] =  pn.Column(
    pn.panel(visualizer.view, sizing_mode='stretch_width'),
    sizing_mode='stretch_both'
)

pn.serve(template)