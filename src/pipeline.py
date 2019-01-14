import argparse
import yaml
import os
import subprocess

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)))


def data_standardization(config_file, DATA_FP, verbose, forceupdate=False):
    """
    Standardize data from a csv file into compatible crashes and concerns
    according to a config file
    Args:
        config_file
        DATA_FP - data directory for this city
        verbose - if we have verbose diagnostics
        forceupdate - whether to restandardize even if files already exist
    """

    if not os.path.exists(os.path.join(DATA_FP, 'standardized', 'crashes.json')) or forceupdate:
        subprocess.check_call([
            'python',
            '-m',
            'data_standardization.standardize_crashes',
            '-c',
            config_file,
            '-d',
            DATA_FP,
            '-v',
            verbose
        ])
    else:
        print("Already standardized crash data, skipping")


def data_generation(config_file, DATA_FP, startdate=None, enddate=None,
                    forceupdate=False):
    """
    Generate the map and feature data for this city
    Args:
        config_file - path to config file
        DATA_FP - path to data directory, e.g. ../data/boston/
        startdate (optional)
        enddate (optional)
    """
    print("Generating data and features...")
    subprocess.check_call([
        'python',
        '-m',
        'data.make_dataset',
        '-c',
        config_file,
        '-d',
        DATA_FP
    ]
        + (['-s', str(startdate)] if startdate else [])
        + (['-e', str(enddate)] if enddate else [])
        + (['--forceupdate'] if forceupdate else [])
    )


def train_model(config_file, DATA_FP):
    """
    Trains the model
    Args:
        config_file - path to config file
        DATA_FP - path to data directory, e.g. ../data/boston/
    """
    print("Training model...")
    subprocess.check_call([
        'python',
        '-m',
        'models.train_model',
        '-c',
        config_file,
        '-d',
        DATA_FP
    ])


def visualize(DATA_FP):
    """
    Creates the visualization data set for a city
    Args:
        DATA_FP - path to data directory, e.g. ../data/boston/
    """
    print("Generating visualization data")
    subprocess.check_call([
        'python',
        '-m',
        'data.make_preds_viz',
        '-c',
        config_file,
        '-d',
        DATA_FP
    ])


if __name__ == '__main__':

    # Parse in arguments from the command line.
    # --config_file for config file
    # --forceupdate to force update on maps
    # --onlysteps to choose which steps to run
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config_file", required=True, type=str, help="config file location")
    parser.add_argument('--forceupdate', action='store_true', help='Whether to force update the maps')
    parser.add_argument('--onlysteps', help="Give list of steps to run, as comma-separated string.  Has to be among 'standardization', 'generation', 'model', 'visualization'")
    parser.add_argument("-v", "--verbose", required=False, default=False, help="Verbose diagnostics: True or False")
    args = parser.parse_args()

    # If 'onlysteps' is specified, split the steps into list
    if args.onlysteps:
        steps = args.onlysteps.split(',')

    # Read the config_file and create various variables from it.
    with open(args.config_file) as f:
        config = yaml.safe_load(f)

    startdate = config['startdate']
    enddate = config['enddate']

    DATA_FP = os.path.join(BASE_DIR, 'data', config['name'])

    if not args.onlysteps or 'standardization' in args.onlysteps:
        print('Running data standardization')
        if args.verbose:
            print('Args.config_file:', args.config_file)
            print('DATA_FP:', DATA_FP)
            print('forceupdate', args.forceupdate)
        data_standardization(args.config_file, DATA_FP, verbose=args.verbose, forceupdate=args.forceupdate)

    if not args.onlysteps or 'generation' in args.onlysteps:
        print('Running data generation')
        data_generation(args.config_file, DATA_FP,
                        startdate=startdate,
                        enddate=enddate,
                        forceupdate=args.forceupdate)

    if not args.onlysteps or 'model' in args.onlysteps:
        print('Running train model')
        train_model(args.config_file, DATA_FP)

    if not args.onlysteps or 'visualization' in args.onlysteps:
        print('Running visualisation')
        visualize(DATA_FP)
