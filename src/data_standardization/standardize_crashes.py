# Standardize crash data from VicRoads
import argparse
import os
import pandas as pd
import yaml
import sys

pd.options.mode.chained_assignment = None


def read_clean_combine_crash(RAW_CRASH_DIR):
    # Get file names and read in csv's
    crash_file = os.path.join(RAW_CRASH_DIR, 'crash.csv')
    map_file = os.path.join(RAW_CRASH_DIR, 'map.csv')
    map_inters_file = os.path.join(RAW_CRASH_DIR, 'map_inters.csv')
    atmosphere_file = os.path.join(RAW_CRASH_DIR, 'atmosphere.csv')

    crash_df = pd.read_csv(crash_file)
    map_df = pd.read_csv(map_file)
    map_inters_df = pd.read_csv(map_inters_file)
    atmosphere_df = pd.read_csv(atmosphere_file)

    # crash_df: drop unwanted columns and establish mappings
    crash_df_cols_reduced = ['ACCIDENT_NO', 'ACCIDENTDATE', 'ACCIDENTTIME', 'DAY_OF_WEEK', 'LIGHT_CONDITION', 'NODE_ID', 'ROAD_GEOMETRY', 'SPEED_ZONE']
    geom_mapping_cols = ['ROAD_GEOMETRY', 'Road Geometry Desc']
    accident_type_mapping_cols = ['ACCIDENT_TYPE', 'Accident Type Desc']
    DCA_code_mapping_cols = ['DCA_CODE', 'DCA Description']
    light_condition_mapping_cols = ['LIGHT_CONDITION', 'Light Condition Desc']

    geom_mapping = crash_df[geom_mapping_cols]
    geom_mapping = geom_mapping.drop_duplicates().sort_values(by='ROAD_GEOMETRY').reset_index(drop=True)

    accident_type_mapping = crash_df[accident_type_mapping_cols]
    accident_type_mapping = accident_type_mapping.drop_duplicates().sort_values(by='ACCIDENT_TYPE').reset_index(drop=True)

    light_condition_mapping = crash_df[light_condition_mapping_cols]
    light_condition_mapping = light_condition_mapping.drop_duplicates().sort_values(by='LIGHT_CONDITION').reset_index(drop=True)

    DCA_code_mapping = crash_df[DCA_code_mapping_cols]
    DCA_code_mapping = DCA_code_mapping.drop_duplicates().sort_values(by="DCA_CODE").reset_index(drop=True)

    crash_df_reduced = crash_df[crash_df_cols_reduced]

    # Map_df: drop unwanted columns, create node type mapping
    node_type_mapping = pd.DataFrame({'NODE_TYPE_INT': [0, 1, 2, 3], 'NODE_TYPE': ['I', 'N', 'O', 'U'], 'NODE_DESC': ['Intersection', 'Non-intersection', 'Off-road', 'Unknown']})

    map_df['NODE_TYPE_INT'] = ""
    for index, row in node_type_mapping.iterrows():
        map_df['NODE_TYPE_INT'].loc[map_df['NODE_TYPE'] == row['NODE_TYPE']] = row['NODE_TYPE_INT']

    map_df_reduced_cols = ['ACCIDENT_NO', 'NODE_ID', 'NODE_TYPE_INT', 'LGA_NAME', 'Deg Urban Name', 'Lat', 'Long']
    map_df_reduced = map_df[map_df_reduced_cols]

    # map_iters_df: drop unwanted columns, creat node-to-complex node mapping
    complex_node_mapping_cols = ['NODE_ID', 'COMPLEX_INT_NO']
    complex_node_mapping = map_inters_df[complex_node_mapping_cols]
    complex_node_mapping = complex_node_mapping.drop_duplicates().sort_values(by="NODE_ID").reset_index(drop=True)

    map_inters_df_reduced = map_inters_df[['ACCIDENT_NO', 'COMPLEX_INT_NO']]

    # atmosphere_df: drop unwanted columns, create atmosphere mapping
    atmosphere_mapping_cols = ['ATMOSPH_COND', 'Atmosph Cond Desc']
    atmosphere_mapping = atmosphere_df[atmosphere_mapping_cols]
    atmosphere_mapping = atmosphere_mapping.drop_duplicates().sort_values(by="ATMOSPH_COND").reset_index(drop=True)

    atmosphere_df_reduced_cols = ['ACCIDENT_NO', 'ATMOSPH_COND']
    atmosphere_df_reduced = atmosphere_df[atmosphere_df_reduced_cols]

    # Drop duplicates from all dataframes
    # Note: most of these duplicates are legitimate
    # Chain effects of a crash are given different incident numbers. We will treat it as one crash however.
    crash_df_reduced.drop_duplicates(subset="ACCIDENT_NO", inplace=True)
    map_df_reduced.drop_duplicates(subset="ACCIDENT_NO", inplace=True)
    map_inters_df_reduced.drop_duplicates(subset="ACCIDENT_NO", inplace=True)
    atmosphere_df_reduced.drop_duplicates(subset="ACCIDENT_NO", inplace=True)

    # Begin joining dataframes on 'ACCIDENT_NO'.
    # Joining by 'outer', means that if some accident numbers are in one DF but not in another, the accident will still be recorded but will be missing columns
    # The validate option ensures that when merging, each DF only has one instance of each accident number
    crashes_and_atmos = pd.merge(crash_df_reduced, atmosphere_df_reduced, on='ACCIDENT_NO', how='outer', validate='one_to_one')
    inters_and_complex = pd.merge(map_df_reduced, map_inters_df_reduced, on='ACCIDENT_NO', how='outer', validate='one_to_one')
    crashes_df = pd.merge(crashes_and_atmos, inters_and_complex, on='ACCIDENT_NO', how='outer', validate='one_to_one')

    # Many NA's within the 'COMPLEX_INT_NO' column. Fill some of these.
    # Some NA's associated with strange NODE_ID's from original crash DF, meaning we couldn't map to Lat / Lon. Remove these.
    # Drop the extra 'NODE_ID' column we have gained
    crashes_df['COMPLEX_INT_NO'] = crashes_df['COMPLEX_INT_NO'].fillna(0)
    crashes_df.dropna(subset=['Lat', 'Long'], inplace=True)
    crashes_df.drop(['NODE_ID_y'], axis=1, inplace=True)

    # Make sure there are no more NA values left anywhere within DF
    if len(crashes_df[crashes_df.isna().any(axis=1)]) != 0:
        print('There are still NA values left within crashes_df during standardization')
        print('Please check this manually. Exiting.')
        sys.exit(1)

    # Standardize column names
    crashes_df.rename(columns={"NODE_ID_x": "NODE_ID", "ACCIDENTDATE": "ACCIDENT_DATE", "ACCIDENTTIME": "ACCIDENT_TIME",
                               "LGA_NAME": "SUBURB", "Deg Urban Name": "DEGREE_URBAN", "Lat": "LAT", "Long": "LON", "LIGHT_CONDITION": "LIGHT_COND"}, inplace=True)

    # Change dtype of columns to integers [these were changed due to the merge step creating NA values]
    crashes_df[['NODE_ID', 'COMPLEX_INT_NO']] = crashes_df[['NODE_ID', 'COMPLEX_INT_NO']].astype(int)

    # Feature engineering
    # Add a binary value for if a crash occured at a complex node
    # Add values for Hour / Month as seasonality features
    crashes_df['COMPLEX_NODE'] = 0
    crashes_df['COMPLEX_NODE'].loc[crashes_df['COMPLEX_INT_NO'] > 0] = 1
    crashes_df['DATE_TIME'] = pd.to_datetime(crashes_df['ACCIDENT_DATE'] + " " + crashes_df['ACCIDENT_TIME'], format="%d/%m/%Y %H.%M.%S")
    crashes_df['HOUR'] = crashes_df.DATE_TIME.dt.hour
    crashes_df['MONTH'] = crashes_df.DATE_TIME.dt.month

    # Once again drop unwanted columns
    crashes_df.drop(['ACCIDENT_DATE', 'ACCIDENT_TIME', 'COMPLEX_INT_NO'], axis=1, inplace=True)

    # Reorder columns for easier reading
    crashes_df = crashes_df[['ACCIDENT_NO', 'DATE_TIME', 'MONTH', 'HOUR', 'DAY_OF_WEEK', 'LAT', 'LON', 'SUBURB', 'NODE_ID', 'NODE_TYPE_INT', 'COMPLEX_NODE', 'LIGHT_COND', 'ATMOSPH_COND', 'SPEED_ZONE', 'ROAD_GEOMETRY', 'DEGREE_URBAN']]

    # Set 'ACCIDENT_NO' to be the index
    crashes_df.set_index('ACCIDENT_NO', inplace=True)

    # Put various mappings into a tuple to allow for easier transport
    mappings = (geom_mapping, accident_type_mapping, DCA_code_mapping, light_condition_mapping, node_type_mapping, atmosphere_mapping)

    return crashes_df, mappings


def output_crash_csv(PROCESSED_CRASH_DIR, PROCESSED_MAPPING_DIR, crashes_df, mappings):

    geom_mapping, accident_type_mapping, DCA_code_mapping, light_condition_mapping, node_type_mapping, atmosphere_mapping = mappings

    # Output resulting crashes_df and all mappings
    if not os.path.exists(PROCESSED_CRASH_DIR):
        os.makedirs(PROCESSED_CRASH_DIR)

    if not os.path.exists(PROCESSED_MAPPING_DIR):
        os.makedirs(PROCESSED_MAPPING_DIR)

    crashes_path = os.path.join(PROCESSED_CRASH_DIR, 'crashes.csv')
    crashes_df.to_csv(crashes_path)

    mapping_dfs = [geom_mapping, accident_type_mapping, DCA_code_mapping,
                   light_condition_mapping, node_type_mapping, atmosphere_mapping]
    mapping_names = ['geom_mapping.csv', 'accident_type_mapping.csv', 'DCA_code_mapping.csv',
                     'light_condition_mapping.csv', 'node_type_mapping.csv', 'atmosphere_mapping.csv']

    for mapping_df, mapping_name in zip(mapping_dfs, mapping_names):
        save_path = os.path.join(PROCESSED_MAPPING_DIR, mapping_name)
        mapping_df.to_csv(save_path)


def output_crash_json(PROCESSED_CRASH_DIR, crashes_df):
    output_file = PROCESSED_CRASH_DIR + '/crashes.json'
    crashes_df.to_json(output_file, orient='index')


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str, required=True,
                        help="config file")
    parser.add_argument("-d", "--datadir", type=str, required=True,
                        help="data directory")
    parser.add_argument("-v", "--verbose", type=bool, required=False,
                        help="verbose logging: True or False")
    args = parser.parse_args()

    # Load config
    config_file = args.config
    data_dir = args.datadir
    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Define file paths and check directories exist
    RAW_DIR = os.path.join(data_dir, "raw")
    RAW_CRASH_DIR = os.path.join(RAW_DIR, 'crash')
    PROCESSED_CRASH_DIR = os.path.join(data_dir, 'processed', 'crash')
    PROCESSED_MAPPING_DIR = os.path.join(data_dir, 'processed', 'mapping')

    if not os.path.exists(RAW_CRASH_DIR):
        print('Did not find data_dir file')
        raise SystemExit(RAW_CRASH_DIR + " not found, exiting")

    crashes_df, mappings = read_clean_combine_crash(RAW_CRASH_DIR)
    output_crash_csv(PROCESSED_CRASH_DIR, PROCESSED_MAPPING_DIR, crashes_df, mappings)
    output_crash_json(PROCESSED_CRASH_DIR, crashes_df)
