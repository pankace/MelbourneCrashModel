# Need to be able to process batch and single results
# Need to load in data with near_id

import pandas as pd
import os
import argparse
import yaml
from datetime import datetime
import sys
import pickle

CURR_FP = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURR_FP)

from model_utils import format_crash_data
from model_classes import Indata, Tuner, Tester
from train_model import process_features, get_features
import sklearn.linear_model as skl


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__))))


def predict(trained_model, predict_data, features, data_model_features, DATA_DIR):
    """
    Returns
        nothing, writes prediction segments to file
    """

    # Ensure predict_data has the same columns and column ordering as required by trained_model
    predict_data_reduced = predict_data[data_model_features]
    preds = trained_model.predict_proba(predict_data_reduced)[::, 1]
    predict_data['predictions'] = preds

    predict_data.to_csv(os.path.join(DATA_DIR, 'predictions.csv'), index=False)
    predict_data.to_json(os.path.join(DATA_DIR, 'predictions.json'), orient='index')


def get_accident_count_recent(predict_data, data):
    data['DATE_TIME'] = pd.to_datetime(data['DATE_TIME'])

    current_date = datetime.now()
    past_7_days = current_date - pd.to_timedelta("7day")
    past_30_days = current_date - pd.to_timedelta("30day")
    past_365_days = current_date - pd.to_timedelta("365day")
    past_1825_days = current_date - pd.to_timedelta("1825day")
    past_3650_days = current_date - pd.to_timedelta("3650day")

    recent_crash_7 = data.loc[data['DATE_TIME'] > past_7_days]
    recent_crash_30 = data.loc[data['DATE_TIME'] > past_30_days]
    recent_crash_365 = data.loc[data['DATE_TIME'] > past_365_days]
    recent_crash_1825 = data.loc[data['DATE_TIME'] > past_1825_days]
    recent_crash_3650 = data.loc[data['DATE_TIME'] > past_3650_days]

    column_names = ['LAST_7_DAYS', 'LAST_30_DAYS', 'LAST_365_DAYS', 'LAST_1825_DAYS', 'LAST_3650_DAYS']
    recent_crashes = [recent_crash_7, recent_crash_30, recent_crash_365, recent_crash_1825, recent_crash_3650]

    for col_name in column_names:
        predict_data[col_name] = ""

    i = 0
    print('About to append recent accident counts. This will take some time.')
    for i in range(len(predict_data)):
        current_segment_id = predict_data.loc[i].segment_id

        for j in range(len(recent_crashes)):

            # Find number of crashes at same segment that have occured in appropriate time period
            recent_crash = recent_crashes[j]
            num_crashes = len(recent_crash.loc[recent_crash['segment_id'] == current_segment_id])

            # Assign this number to predict_data
            col_name = column_names[j]
            predict_data.at[i, col_name] = num_crashes

        if i % 5000 == 0:
            print("Got through {}% of results".format(100 * i / len(predict_data)))

    return predict_data


def add_empty_features(predict_data, features):

    # Read in the features from our modelling dataset
    features_path = os.path.join(PROCESSED_DIR, 'features.pk')
    with open(features_path, 'rb') as fp:
        data_model_features = pickle.load(fp)

    # Get the difference of features between our modelling dataset and predicting dataset
    # Recast as a list to allow for looping over
    feature_difference = list(set(data_model_features) - set(features))

    # Add features in a loop as python doens't like adding all at one time
    for feat in feature_difference:
        predict_data[feat] = 0

    return predict_data, feature_difference, data_model_features


if __name__ == '__main__':

    print('Within train_model.py')
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', type=str, help="yml file for model config, default is a base config with open street map data and crashes only")
    parser.add_argument('-d', '--DATA_DIR', type=str, help="data directory")
    parser.add_argument('-f', '--forceupdate', type=str, help="force update our data model or not", default=False)
    args = parser.parse_args()

    config = {}
    if args.config:
        config_file = args.config
        with open(config_file) as f:
            config = yaml.safe_load(f)

    # Create required data paths
    DATA_DIR = os.path.join(BASE_DIR, 'data', config['name'])
    PROCESSED_DIR = os.path.join(BASE_DIR, 'data', config['name'], 'processed/')
    crash_data_path = os.path.join(PROCESSED_DIR, 'crash.csv.gz')
    road_data_path = os.path.join(PROCESSED_DIR, 'roads.csv.gz')

    # Read in road data. We shall generate a prediction for each segment.
    # predict_data = pd.read_csv(road_data_path)
    # Use pk rather than csv to keep datatypes correct
    with open(os.path.join(PROCESSED_DIR, 'roads.pk'), 'rb') as fp:
        predict_data = pickle.load(fp)

    # Reset the index so that it can be properly looped over in the attach accident count phase
    # Drop because there should already be a correlate_id within the DF, was a duplicate
    predict_data.reset_index(inplace=True, drop=True)

    # Read in crash data. We shall use this to attach historic accident counts to road data.
    data = pd.read_csv(crash_data_path)

    # Check NA within both DF
    predict_na = (predict_data.isna().sum()) / len(predict_data)
    data_na = (data.isna().sum()) / len(data)

    data_cols = (data_na < 0.95).keys()
    predict_cols = (predict_na < 0.95).keys()

    print('Removing {} columns from predict data due to NA'.format(set(list(predict_data)) - set(predict_cols)))
    print('Removing {} columns from crash data due to NA'.format(set(list(data)) - set(data_cols)))

    predict_data = predict_data[predict_cols]
    data = data[data_cols]

    predict_data.fillna('', inplace=True)
    data.fillna('', inplace=True)

    # Attach current date / time data
    date_time = datetime.now()
    hour = date_time.hour
    day = date_time.weekday()
    month = date_time.month

    predict_data['MONTH'] = month
    predict_data['DAY_OF_WEEK'] = day
    predict_data['HOUR'] = hour

    # Attach accident data
    predict_path = os.path.join(PROCESSED_DIR, 'predict.csv.gz')
    if not os.path.exists(predict_path) or args.forceupdate:
        predict_data = get_accident_count_recent(predict_data, data)
        predict_data.to_csv(predict_path, index=False, compression='gzip')
    else:
        predict_data = pd.read_csv(predict_path)

    # Get feature lists
    f_cont, f_cat, features = get_features(config, predict_data, PROCESSED_DIR)

    # Process features as in train_model
    predict_data, features, _ = process_features(predict_data, features, config, f_cat, f_cont)

    # Add empty columns for those columns that occur in the training of the model, but didn't occcur in prediction
    # Should expect a whole lot of time columns to be in added_features, as our prediction uses only datetime.now()
    predict_data, added_features, data_model_features = add_empty_features(predict_data, features)

    # Read in best performing model from train_model
    with open(os.path.join(PROCESSED_DIR, 'model.pk'), 'rb') as fp:
        trained_model = pickle.load(fp)

    # Get predictions from model and prediction features
    predict(trained_model=trained_model, predict_data=predict_data, features=features, data_model_features=data_model_features, DATA_DIR=DATA_DIR)
