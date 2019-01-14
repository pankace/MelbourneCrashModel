import numpy as np
import pandas as pd
import scipy.stats as ss
import os
import json
import argparse
import yaml
import sys

CURR_FP = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURR_FP)

from model_utils import format_crash_data
from model_classes import Indata, Tuner, Tester
import sklearn.linear_model as skl

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__))))


def get_features(config, data, datadir):
    """
    Get features from the feature list created during data generation / or the list specified during init_city.
    """

    cont_feat = config['cont_feat']
    cat_feat = config['cat_feat']

    # Dropping continuous features that don't exist
    cont_feat_found = []
    for f in cont_feat:
        if f not in data.columns.values:
            print("Feature " + f + " not found, skipping")
        else:
            cont_feat_found.append(f)

    # Dropping categorical features that don't exist
    cat_feat_found = []
    for f in cat_feat:
        if f not in data.columns.values:
            print("Feature " + f + " not found, skipping")
        else:
            cat_feat_found.append(f)

    # Create featureset holder
    features = cont_feat_found + cat_feat_found

    return cont_feat_found, cat_feat_found, features


def process_features(data, features, config, f_cat, f_cont):

    print('Within train_model.process_features')

    # Features for linear model
    linear_model_features = features

    # Turn categorical variables into one-hot representation through get_dummies
    # Append the newly named one-hot variables [e.g. hwy_type23] to our data frame
    # Append the new feature names to our feature list
    # For linear model features leave out the first one [e.g. hwy_type0 for intercept (?)]
    print('Processing categorical variables [one-hot encoding]')
    for f in f_cat:
        temp = pd.get_dummies(data[f])
        temp.columns = [f + '_' + str(c) for c in temp.columns]
        data = pd.concat([data, temp], axis=1)
        features += temp.columns.tolist()
        linear_model_features += temp.columns.tolist()[1:]

    # Turn continuous variables into their log [add one to avoid -inf errors]
    # Using 1.0 rather than 1 to typecast as float rather than int. This is required for log transform [base e].
    # Also requires a temp array to hold the values with a recasting, otherwise numpy tries to do things like 5.log, rather than log(5)
    # Append new feature name to relevant lists[e.g. log_width]
    print('Processing continuous variables [log-transform]')
    for f in f_cont:
        temp_array = np.array((data[f] + 1).values).astype(np.float64)
        data['log_%s' % f] = np.log(temp_array)
        features += ['log_%s' % f]
        linear_model_features += ['log_%s' % f]

    # Remove duplicated features
    # e.g. if features = ['a', 'b', 'c', 'b'], f_cat = ['a'] and f_cont=['b']
    # then set(features) = {'a', 'b', 'c'} and set(f_cat + f_cont) = {'a', 'b'}

    features = list(set(features) - set(f_cat + f_cont))
    linear_model_features = list(set(linear_model_features) - set(f_cat + f_cont))

    return data, features, linear_model_features


def output_importance(trained_model, features, datadir):
    # output feature importances or coefficients
    if hasattr(trained_model, 'feature_importances_'):
        feature_imp_dict = dict(zip(features, trained_model.feature_importances_.astype(float)))
    elif hasattr(trained_model, 'coefficients'):
        feature_imp_dict = dict(zip(features, trained_model.coefficients.astype(float)))
    else:
        return("No feature importances/coefficients detected")
    # conversion to json
    with open(os.path.join(datadir, 'feature_importances.json'), 'w') as f:
        json.dump(feature_imp_dict, f)


def set_params():

    # cv parameters
    cvp = dict()
    cvp['pmetric'] = 'roc_auc'
    cvp['iter'] = 5  # number of iterations
    cvp['folds'] = 5  # folds for cv (default)
    cvp['shuffle'] = True

    # LR parameters
    mp = dict()
    mp['LogisticRegression'] = dict()
    mp['LogisticRegression']['penalty'] = ['l2']
    mp['LogisticRegression']['C'] = ss.beta(a=5, b=2)  # beta distribution for selecting reg strength
    mp['LogisticRegression']['class_weight'] = ['balanced']
    mp['LogisticRegression']['solver'] = ['lbfgs']

    # xgBoost model parameters
    mp['XGBClassifier'] = dict()
    mp['XGBClassifier']['max_depth'] = list(range(3, 7))
    mp['XGBClassifier']['min_child_weight'] = list(range(1, 5))
    mp['XGBClassifier']['learning_rate'] = ss.beta(a=2, b=15)

    # cut-off for model performance
    # generally, if the model isn't better than chance, it's not worth reporting
    perf_cutoff = 0.5
    return cvp, mp, perf_cutoff


def initialize_and_run(data_model, features, linear_model_features, datadir, target, seed=None):

    print('Within train_model.initialize_and_run')
    print('Will now set initial model parameters, created our InData object, split into train / test sets')

    # Cross-validation parameters, model parameters, perf_cutoff
    cvp, mp, perf_cutoff = set_params()

    # Initialize data with __init__ method
    # Parameters (self, data, target, scoring=None
    # Returns object with properties: .data, .target, .scoring [if provided]
    # With attributes: scoring, data, train_x, train_y, test_x, test_y, is_split
    df = Indata(data_model, target)

    # Create train/test split
    # Parameters (self, pct, datesort=None, group_col=None, seed=None)
    df.tr_te_split(.7, seed=seed)

    # Create weighting variable and attach to parameters
    # This is intended to weight data if it is imbalanced.
    # a[0] = frequency of negative class, a[1] = frequency of positive class
    # normalize = True means .value_counts returns relative frequencies, not absolute count
    a = data_model[target].value_counts(normalize=True)
    w = 1 / a[1]
    mp['XGBClassifier']['scale_pos_weight'] = [w]

    # Initialize tuner
    # Tuner takes the attributes [self, indata, best_models=None, grid_results=None)]
    print('Having done our base initialisation, we attempt to tune model using tuner object')
    tune = Tuner(df)
    try:
        # Base XGBoost model and then base Logistic Regression model
        # Tuning method has the parameters [self, name, m_name, features, cvparams, mparams]
        tune.tune('XG_base', 'XGBClassifier', features, cvp, mp['XGBClassifier'])
        tune.tune('LR_base', 'LogisticRegression', linear_model_features, cvp, mp['LogisticRegression'])

    except ValueError:
        print('CV fails, likely very few of target available, try rerunning at segment-level')
        raise

    # Initialise and run tester object to find best performing model
    print('Tuning finished, running against test data')
    test = Tester(df)
    test.init_tuned(tune)
    test.run_tuned('LR_base', cal=False)
    test.run_tuned('XG_base', cal=False)

    # choose best performing model
    print('Within train_model. Have instantiated tuner object and completed tuning. Will now iterate over test.rundict to check for best performing model. Test.rundict has len:', len(test.rundict), 'and looks like:', test.rundict)
    best_perf = 0
    best_model = None
    for m in test.rundict:
        if test.rundict[m]['roc_auc'] > best_perf:
            best_perf = test.rundict[m]['roc_auc']
            best_model = test.rundict[m]['model']
            best_model_features = test.rundict[m]['features']

    # Check for performance above certain level
    if best_perf <= perf_cutoff:
        print(('Model performs below AUC %s, may not be usable' % perf_cutoff))

    # Train on full data
    print('Best performance was', best_perf, '\n Best model was', best_model, '\nBest model features were', best_model_features)
    trained_model = best_model.fit(data_model[best_model_features], data_model[target])

    # Output feature importance
    output_importance(trained_model, features, datadir)

    # Save out best model to pickle for later use
    with open(os.path.join(datadir, 'model.pk'), 'wb') as fp:
        pickle.dump(trained_model, fp)


if __name__ == '__main__':

    print('Within train_model.py')
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', type=str, help="yml file for model config, default is a base config with open street map data and crashes only")
    parser.add_argument('-d', '--datadir', type=str, help="data directory")
    parser.add_argument('-f', '--forceupdate', type=str, help="force update our data model or not", default=False)
    args = parser.parse_args()

    config = {}
    if args.config:
        config_file = args.config
        with open(config_file) as f:
            config = yaml.safe_load(f)

    # Print out various inputs for sanity
    print('Parsed -config as', args.config, '\n', '-datadir as', args.datadir)
    print('Reading in seg_data from config[seg_data] at: \n\n', config['seg_data'])
    print('Config file looks like \n \n', config, '\n\n')

    # Create required data paths
    DATA_DIR = os.path.join(BASE_DIR, 'data', config['name'])
    PROCESSED_DATA_DIR = os.path.join(BASE_DIR, 'data', config['name'], 'processed/')
    merged_data_path = os.path.join(PROCESSED_DATA_DIR, config['merged_data'])
    print(('Outputting to: %s' % PROCESSED_DATA_DIR))

    # Read in data
    data = pd.read_csv(merged_data_path)
    data.sort_values(['DATE_TIME'], inplace=True)

    # Get all features that exist within dataset and are being used
    f_cont, f_cat, features = get_features(config, data, PROCESSED_DATA_DIR)
    print('Our categorical features are:', f_cat)
    print('Our continuous features are:', f_cont)

    # Remove features that aren't part of f_cat or f_cont or TARGET
    data_model = data[f_cat + f_cont + ['TARGET']]

    # Add one-hot representations of our categorical features
    # Add log transform representations of our continuous features
    data_model, features, linear_model_features = process_features(data_model, features, config, f_cat, f_cont)

    # Print out various statistics to understand model parameters
    print("full features:{}".format(features))
    print('\n\n Data_model: \n\n', data_model)
    print('\n\n features:', features)
    print('\n\n lm_features:', linear_model_features)
    print('\n\n Process_DATA_DIR:', PROCESSED_DATA_DIR)

    # Save out data_model and the features within
    data_model_path = os.path.join(PROCESSED_DATA_DIR, 'myDataModel.csv')
    if not os.path.exists(data_model_path) or args.forceupdate:
        data_model.to_csv(data_model_path, index=False)

    features_path = data_model_path = os.path.join(PROCESSED_DATA_DIR, 'features.pk')
    if not os.path.exists(features_path) or args.forceupdate:
        with open(features_path, 'wb') as fp:
            pickle.dump(features, fp)

    initialize_and_run(data_model, features, linear_model_features, PROCESSED_DATA_DIR, target='TARGET')
