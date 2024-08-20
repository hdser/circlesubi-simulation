def update_time(params, substep, state_history, prev_state, policy_input, **kwargs):
    """Update simulation time."""
    current_time = prev_state['time'] + params['interaction_period']
    return 'time', current_time
