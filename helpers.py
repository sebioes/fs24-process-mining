def fold_outcome(row, indicator_list=[]):
    for outcome in indicator_list:
        if row[outcome]:
            return outcome
    return 'unresolved'

