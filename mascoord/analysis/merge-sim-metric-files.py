import os
import pandas as pd
import numpy as np
import tqdm

keywords = [
    ('-c-cocoa-', 'max-deg-6', 'dc-cocoa-d10'),
    # ('c-cocoa', 'max-deg-3', 'c-cocoa')
]
metrics_dir = '../metrics-collected-on-21-04-2022/'


def main():
    files_count_dict = {}
    errored_files = []
    for kwd in tqdm.tqdm(keywords):
        data_files = [f for f in os.listdir(metrics_dir) if kwd[0] in f and kwd[1] in f and '.csv' in f]
        files_count_dict[kwd] = len(data_files)

        if data_files:
            dataframes = [pd.read_csv(f'{metrics_dir}/{metrics_file}') for metrics_file in data_files]
            # print([df.shape for df in dataframes])
            df_merged = pd.DataFrame()

            # select one df to copy invariable values
            for df in dataframes:
                if df.shape[0] == 120:
                    df_merged['event'] = df['event']
                    df_merged['type'] = df['type']
                    df_merged['num_agents'] = df['num_agents']
                    break

            data_columns = dataframes[0].columns[3:]
            for col in data_columns:
                col_data = []
                for i, df in enumerate(dataframes):
                    if df.shape[0] == 120:
                        col_data.append(df[col])
                    elif data_files[i] not in errored_files:
                        errored_files.append(data_files[i])
                col = 'edge_' + col if col == 'cost' else col

                df_merged[col] = np.mean(col_data, axis=0)
                df_merged[col + '-std'] = np.std(col_data, axis=0)

            filename = f'{kwd[2]}-{kwd[1]}-merged-metrics.csv'
            df_merged.to_csv(f'./{filename}', index=False)

    print(files_count_dict)
    print(f'{len(errored_files)} errored files: {errored_files}')


if __name__ == '__main__':
    main()
