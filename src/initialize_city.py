import argparse
import os
import shutil
import tzlocal
from data.util import geocode_address

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_config_file(yml_file, timezone, city, folder, crash_file_path, map_file_path, map_inters_file_path, atmosphere_file_path, merged_file_path, cat_feat, cont_feat, keep_feat):

    address = geocode_address(city)

    f = open(yml_file, 'w')
    f.write(
        "# City name\n" +
        "city: {}\n".format(city) +
        "# City centerpoint latitude & longitude\n" +
        "city_latitude: {}\n".format(address[1]) +
        "city_longitude: {}\n".format(address[2]) +
        "# City's time zone [defaults to local to,e of computer]\n" +
        "timezone: {}\n".format(timezone) +
        "# The folder under data where this city's data is stored\n" +
        "name: {}\n".format(folder) +
        "# Limit crashes to between start and end date\n" +
        "startdate: \n" +
        "enddate: \n" +
        "#################################################################\n" +
        "crash_files:\n" +
        "  {}\n".format(crash_file_path) +
        "  {}\n".format(map_file_path) +
        "  {}\n".format(map_inters_file_path) +
        "  {}\n".format(atmosphere_file_path) +
        "cat_feat: {} \n".format(cat_feat) +
        "cont_feat: {} \n".format(cont_feat) +
        "keep_feat: {} \n".format(keep_feat) +
        "merged_data: {}".format(merged_file_path)
    )

    f.close()
    print("Wrote new configuration file in {}".format(yml_file))


def make_js_config(jsfile, city, folder):
    address = geocode_address(city)

    f = open(jsfile, 'w')
    f.write(
        'var config = {\n' +
        '    MAPBOX_TOKEN: "pk.eyJ1IjoiZGVsZXdpczEzIiwiYSI6ImNqb3BjaTYzaDAwdjQzcWxsa3hsNzFtbmYifQ.yKj5c8ODg6yN0xTwmYS1LQ",\n' +
        '    cities: [\n' +
        '        {\n' +
        '            name: "{}",\n'.format(city) +
        '            id: "{}",\n'.format(folder) +
        '            latitude: {},\n'.format(str(address[1])) +
        '            longitude: {},\n'.format(str(address[2])) +
        '        }\n' +
        '    ]\n' +
        '}\n'
    )
    f.close()


if __name__ == '__main__':

    # Parse our arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-city", "--city", type=str, required=True, help="city name, e.g. 'Boston, Massachusetts, USA'")
    parser.add_argument("-f", "--folder", type=str, required=True, help="folder name, e.g. 'boston'")
    parser.add_argument('--crash', type=str, required=False, help="crash file path")
    parser.add_argument('--mapping', type=str, required=False, help="map crashes to locations")
    parser.add_argument('--intersection_map', type=str, required=False, help="map intersections to complex nodes")
    parser.add_argument('--atmosphere', type=str, required=False, help="atmospheric conditions for crash")
    parser.add_argument('--merged', type=str, required=False, help="merged data file")
    args = parser.parse_args()

    # Commit arguments to variables
    city = args.city
    folder = args.folder

    if args.crash:
        crash_file = args.crash
        map_file = args.mapping
        map_inters_file = args.intersection_map
        atmosphere_file = args.atmosphere
    else:
        print('Using the default raw file locations. If they do not exist, please include raw file path arguments in cmd call.')
        crash_file = 'C:/Users/Daniel/Documents/ML/Transurban V2/data/raw/crash.csv'
        map_file = 'C:/Users/Daniel/Documents/ML/Transurban V2/data/raw/map.csv'
        map_inters_file = 'C:/Users/Daniel/Documents/ML/Transurban V2/data/raw/map_inters.csv'
        atmosphere_file = 'C:/Users/Daniel/Documents/ML/Transurban V2/data/raw/atmosphere.csv'

    # Get our various file paths
    DATA_FP = os.path.join(BASE_DIR, 'data', folder)
    PROCESSED_DIR = os.path.join(DATA_FP, 'processed')
    RAW_DIR = os.path.join(DATA_FP, 'raw')
    RAW_CRASH_DIR = os.path.join(RAW_DIR, 'crash')

    crash_file_path = os.path.join(RAW_CRASH_DIR, 'crash.csv')
    map_file_path = os.path.join(RAW_CRASH_DIR, 'map.csv')
    map_inters_file_path = os.path.join(RAW_CRASH_DIR, 'map_inters.csv')
    atmosphere_file_path = os.path.join(RAW_CRASH_DIR, 'atmosphere.csv')
    merged_file_path = os.path.join(PROCESSED_DIR, 'canon.csv.gz')

    # Define our categorical / continuous features for usage in modelling
    cat_feat = ['HOUR', 'DAY_OF_WEEK', 'MONTH', 'DEGREE_URBAN', 'LIGHT_COND', 'ATMOSPH_COND', 'NODE_TYPE_INT',
                'COMPLEX_INT', 'hwy_type', 'inter', 'intersection_segments', 'lanes', 'oneway', 'signal', 'streets', 'direction']

    cont_feat = ['SPEED_ZONE', 'osm_speed', 'LAST_7_DAYS', 'LAST_30_DAYS', 'LAST_365_DAYS', 'LAST_1825_DAYS', 'LAST_3650_DAYS']

    # Define our features to keep until the last step where we strip down to modelling features
    keep_feat = cat_feat + cont_feat + ['display_name', 'intersection', 'segment_id']

    # Create our data paths
    if not os.path.exists(DATA_FP):
        print("Making directory structure under " + DATA_FP)
        os.makedirs(DATA_FP)
        os.makedirs(os.path.join(DATA_FP, 'raw'))
        os.makedirs(os.path.join(DATA_FP, 'processed'))
        os.makedirs(os.path.join(DATA_FP, 'standardized'))
        os.makedirs(RAW_CRASH_DIR)

        # We copy across all raw data files.
        # Note: Merged is not copied because not yet created.
        shutil.copyfile(crash_file, crash_file_path)
        shutil.copyfile(map_file, map_file_path)
        shutil.copyfile(map_inters_file, map_inters_file_path)
        shutil.copyfile(atmosphere_file, atmosphere_file_path)
    else:
        print(folder + "folder already initialized, skipping")

    # Create our yml config file
    yml_file = os.path.join(BASE_DIR, 'src/config/' + folder + '.yml')
    if not os.path.exists(yml_file):
        make_config_file(yml_file, tzlocal.get_localzone().zone, city, folder, crash_file_path, map_file_path, map_inters_file_path, atmosphere_file_path, merged_file_path, cat_feat, cont_feat, keep_feat)

    # Create our js config file
    reports_file_path = os.path.join(BASE_DIR, 'reports', folder)
    print(reports_file_path)
    if not os.path.exists(reports_file_path):
        print('Making reports file path')
        os.makedirs(reports_file_path)

    js_file_path = os.path.join(BASE_DIR, 'reports', folder, 'config.js')
    if not os.path.exists(js_file_path):
        print("Writing config.js")
        make_js_config(js_file_path, city, folder)
