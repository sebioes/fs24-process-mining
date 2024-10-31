import pandas as pd


def create_case_log(event_log):
    """
    creates an initial case log
    """
    cases = event_log.groupby('case:concept:name')
    case_log = cases.agg(
        start_time=('time:timestamp','first'),
        end_time=('time:timestamp', 'last'),
        no_of_events=('concept:name', 'count'))
    case_log['duration'] = case_log['end_time'] - case_log['start_time']
    return case_log


def compute_sorted_case_id(event, case_log, case_id_col='case:concept:name'):
    """
    prefixes the case id with the start time of the case such that ordering by
    the resulting sorted case id will order cases according to their arrival time
    """
    case_start_time = case_log.at[event[case_id_col], 'start_time']
    return (str(case_start_time)+ '_'+ event[case_id_col])


def event_add_ordered_case_id(event_log, case_log, case_id_col='case:concept:name'):
    """
    enriches the event log with a sorted case id
    """
    event_log['ordered_case_id'] = event_log.apply(compute_sorted_case_id, case_log=case_log, axis=1)
    return event_log


def track_variable(log, column_name, tracking_method, case_id_col='case:concept:name'):
    return track_variables(log, [(column_name, tracking_method)], case_id_col=case_id_col)


def init_value_of_tracking_method(tracking_method):
    HIGHFLOAT = 2000000.0
    match tracking_method:
        case 'latest':
            return None
        case 'count':
            return 0
        case 'sum':
            return 0
        case 'min':
            return HIGHFLOAT
        case 'append':
            return list()
        case _:   
            print('initialization:', tracking_method, 'NOT SUPPORTED')


def track_variables(log, tracking_list, case_id_col='case:concept:name'):
    # Case History Aggregation: keep track of current state of a variable trough history of a case
    # TODO initial value and update method could go into parameters

    value_store = {} # map each tracked variable (incl method) and case to its current value
    added_cols = {} # map each tracked variable (incl method) to a growing list/vector of values
    added_col_names = []

    for (col, method) in tracking_list:
        added_cols[(col, method)] = []

    for index, row in log.iterrows():
        case_id = row[case_id_col]
        for (col, method) in tracking_list:
            if (case_id, col, method) not in value_store:
                value_store[(case_id, col, method)] = init_value_of_tracking_method(method)
            if not pd.isna(row[col]):
                match method:
                    case 'latest':
                        value_store[(case_id, col, method)] = row[col]
                    case 'count':
                        value_store[(case_id, col, method)] = value_store[(case_id, col, method)] + 1
                    case 'max':
                        value_store[(case_id, col, method)] = max(row[col],value_store[(case_id, col, method)])
                    case 'min':
                        value_store[(case_id, col, method)] = min(row[col],value_store[(case_id, col, method)])
                    case 'sum':
                        value_store[(case_id, col, method)] = round(value_store[(case_id, col, method)] + row[col], 2)
                    case 'append':
                        value_store[(case_id, col, method)].append(row[col])
                    case _:   
                        print('update', method, 'NOT SUPPORTED')
            added_cols[(col, method)].append(value_store[(case_id, col, method)])

    for (col, method) in tracking_list:
        tracking_col_name = col+'::'+method
        added_col_names.append(tracking_col_name)
        log[tracking_col_name] = added_cols[(col,method)]
            
    return log


def enrich_with_row_map(log, column_name, mapper):
    log[column_name] = log.apply(mapper, axis=1)
    return log


def convert_name(name):
    return '_'.join(name.split(' '))


def case_add_activity_start_time(case_log, event_log, activity, case_id_col='case:concept:name', time_col='rel_time'):
    """
    enrich a case log by adding the start time of first occurrence of a given activity in each case
    """
    filtered_event_log = event_log[event_log['concept:name']==activity]
    col_name = convert_name(activity) + '::start'
    case_log[col_name] = filtered_event_log.groupby(case_id_col)[time_col].first()
    return case_log


def case_add_activity_start_times(case_log, event_log, case_id_col='case:concept:name', activity_col='concept:name', time_col='rel_time'):
    """
    enrich a case log by adding, for each activity, the start time of it's first occurrence in each case
    """
    cases = event_log.groupby([case_id_col,activity_col])
    activity_starts = cases[time_col].first()
    activities = event_log[activity_col].unique()
    for activity in activities:
        col_name = convert_name(activity) + '::start'
        case_log[col_name] = activity_starts.xs(activity, level=1, axis=0)
    return case_log


def case_add_activity_delay(case_log, activity1, activity2):
    """
    enrich a case log by adding, for a given pair of activities, the delay between their first occurrences in each case
    requires a 'start' time to be present for each activity in the case log
    """
    activity_name1 = convert_name(activity1) 
    activity_name2 = convert_name(activity2)
    col_name = activity_name1 + ':' + activity_name2 + '::delay'
    case_log[col_name] = case_log[activity_name2+'::start'] - case_log[activity_name1+'::start']
    return case_log


def case_add_activity_delays(case_log, event_log, activity_col='concept:name'):
    """
    enrich a case log by adding, for each unordered pair of activities, the delay between their first occurrences in each case
    """
    activities = list(event_log[activity_col].unique())
    first_activities = activities.copy()
    while len(first_activities) > 0:
        first_act = first_activities.pop()
        second_activities = first_activities.copy()
        while len(second_activities) > 0:
            second_act = second_activities.pop()
            case_log = case_add_activity_delay(case_log, first_act, second_act)
    return case_log


def compute_relative_case_time(event, case_log, case_id_col='case:concept:name', time_col='time:timestamp'):
    assert 'start_time' in case_log.columns, 'case log should have a column "start_time"'
    case_start_time = case_log.at[event[case_id_col], 'start_time']
    return (event[time_col] - case_start_time)


def event_log_enricher(event_log, case_log):
    """
    enrich an event log by adding relative time for each event
    """
    event_log['rel_time'] = event_log.apply(compute_relative_case_time, case_log=case_log, axis=1)
    return event_log


def brute_force_case_log_enricher(case_log, event_log, include_time=True, case_id_col='case:concept:name', activity_col='concept:name'):
    """
    enriches a case log by adding for each activity, the number of occurrences in a case, as well as start times and delays
    """
    # TODO relative log time forward and backward
    # TODO generic data attribute enrichment
    cases = event_log.groupby(case_id_col)
    activity_incidence = cases[activity_col].value_counts()
    activities = event_log[activity_col].unique()
    for activity in activities:
        col_name = convert_name(activity)+'::count'
        case_log[col_name] = activity_incidence.xs(activity,level=1, axis=0)
        case_log[col_name] = case_log[col_name].fillna(0)
    if include_time:
        case_log = case_add_activity_start_times(case_log, event_log, case_id_col=case_id_col, activity_col=activity_col)
        case_log = case_add_activity_delays(case_log, event_log, activity_col=activity_col)
    return case_log

