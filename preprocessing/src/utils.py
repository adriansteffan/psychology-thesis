import pandas as pd

import settings


def create_empty_general_exclusion_df(participants):
    exclusion_df = pd.DataFrame({'id': sorted(list(participants))}) \
        .merge(pd.DataFrame({'stimulus': settings.stimuli}), how='cross')
    exclusion_df['excluded'] = ''
    exclusion_df['exclusion_reason'] = ''

    return exclusion_df


def validate_exclusions(exclusion_df, name):

    # check that each participant x stimulus combination only appears once
    if len(exclusion_df.loc[exclusion_df.duplicated(subset=['id', 'stimulus'], keep=False)].index) != 0:
        print(exclusion_df.loc[exclusion_df.duplicated(subset=['id', 'stimulus'], keep=False)])
        exit(f'{name} - Exclusion validation error: Duplicate participant x stimulus combination')

    # check exclusion - exclusion reason
    ERROR_START = f'{name} - Exclusion validation error in entry'
    for i, row in exclusion_df.iterrows():
        if row['excluded'] == 'i':
            if row['exclusion_reason'] and not pd.isna(row['exclusion_reason']) and row['exclusion_reason'] != '':
                print(row['exclusion_reason'])
                exit(f'{ERROR_START}{i+1}: Cannot have exclusion reason for included trials')
        elif row['excluded'] == 'x':
            if not row['exclusion_reason'] or pd.isna(row['exclusion_reason']) or row['exclusion_reason'] == '':
                exit(f'{ERROR_START}{i+1}: No exclusion reason provided')
        else:
            exit(f'{ERROR_START}{i+1}: Excluded can only have values i or x')
