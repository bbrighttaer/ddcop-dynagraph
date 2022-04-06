import os
import pandas as pd
import numpy as np
import tqdm

keywords = ['-c-cocoa-', '-c-sdpop-', '-dcop-base-', 'c-cocoa-max-']
metrics_dir = '../metrics/c-cocoa-dcop-metrics'

for kwd in tqdm.tqdm(keywords):
    data_files = [f for f in os.listdir(metrics_dir) if kwd in f and '.csv' in f]

    if data_files:
        dataframes = [pd.read_csv(f'{metrics_dir}/{metrics_file}') for metrics_file in data_files]

        df_merged = pd.DataFrame()
        df_merged['event'] = dataframes[0]['event']
        df_merged['type'] = dataframes[0]['type']
        df_merged['num_agents'] = dataframes[0]['num_agents']

        data_columns = dataframes[0].columns[3:]
        for col in data_columns:
            col_data = [df[col] for df in dataframes]
            df_merged[col] = np.mean(col_data, axis=0)

        filename = data_files[0].split('.sim')[0] + kwd + 'merged-metrics.csv'
        df_merged.to_csv(f'./{filename}', index=False)
