# Melbourne Crash Predictions

A demonstration of this application can be seen at: 

This machine learning application is piggy-backed from the excellent work done by Data4Democracy carrying out similar work in Boston. 
For more information on the Data4Democracy project, see the D4D_README file included in this repository.

This project uses the XGBoost algorithm to attempt to predict the relative risk level of various road segments in and around the Melbourne CBD.
In addition, it attempts to identify the physical traits of roads that contribute to calculated risk [i.e. presence of traffic lights, pedestrian crossings] with the intent of helping city planners in designing safer road networks.

This project makes use of open-source data available at https://vicroadsopendata-vicroadsmaps.opendata.arcgis.com/ as well as road geometry data from https://www.openstreetmap.org/

# The Data

Data used in this project can be placed into two broad categories:

(1) Road geometry data from OpenStreetMaps [OSM]
- Road type [highway, residential street]
- Road condition
- Number of intersecting segments
- Presence of traffic lights
- Uni- or bi-directional traffic
- Overhead roads
- Pedestrian crossings
- etc.

(2) Crash data from VicRoads:
- Location of crash [lat, lon]
- Weather conditions
- Time of crash
- Street lighting conditions
- Severity of crash
- Number of vehicles involved
- etc.

The road network geometry is obtained via API calls to OSM and is rendered to the screen via LeafletJS.
The VicRoads crash data is then mapped onto the road network based on closest euclidean distance.
Roads segments are given a 1 or 0 dependent on whether they have experienced a crash in the last 2 years.
An equal number of roads that have / have not seen crashes are chosen at random from the set of all roads.
A ML model is trained on this equally split set, with the aim of predicting whether or not a road has seen a crash in the last two years.
Having trained the model, it can then be used to predict relative risk levels of roads [NOTE: it does not calculate absolute risk levels].

# Technologies

This application is primarily python based [pandas, scikit-learn, shapely]. 

The front-end is rendered using basic HTML, CSS and relies on leafletJS and the OSM SDK for overlaying maps.

# Pipeline:

    (1) Parse args
        -c              for config_file [e.g. config/boston.yml]
        --forceupdate   for maps [otherwise already created files are skipped]
        --onlysteps     list of steps:
            "standardization", "generation", "model", "visualization"

    (2) Data Standardization

    (3) Data Generation

    (4) Train Model

    (5) Visualization


## Data Standardization

    (1) Standardize_crashes.py

    (2) Standardize_concerns.py

    (4) Standardize_point_data.py

## Data Generation [data/make_dataset.py]

    (1) Parse args
        -c              for config_file
        -d              for data directory
        -s              for start date [limit crash timeline]
        -e              for end date [limit crash timeline]
        --forceupdate   force update of created directories

    (2) Basic sanity checks to make sure fed in arguments make sense.

    (3) Make feature list
        make_dataset.make_feature_list(config, args.datadir, waze)
        Determines all the features used by the model.
        Starts which a numbr of features drawn from open street maps which include:
                    'f_cat': 'width'
                    'f_cont': 'lanes', 'hwy_type', 'osm_speed', 'signal', 'oneway', 'width_per_lane'
        Checks if 'data_source' is given [adds features if additional data source given]. If it is, adds the features from that data source.
        Checks if wave is given. If it is adds the 'jam_percent' and 'jam' features.
        Checks if 'additional_features' is given. If it is, adds the features from that data source.

        Outputs features.yml which looks like:
            f_cat:
            - width
            - SPEEDLIMIT
            - Struct_Cnd
            - Surface_Tp
            - F_F_Class
            
            f_cont:
            - lanes
            - hwy_type
            - osm_speed
            - signal
            - oneway
            - width_per_lane
            - AADT

    (4) osm_create_maps.py
        Get maps from OpenStreetMap
        Uses osmnx to get a simplified version of OSM maps for cities
        Outputs:
            osm_ways.shp
            osm_nodes.shp
            osm_elements.geojson

    (5) add_waze_data.py
        Updates osm_elements.geojson with waze data and returns jams.geojson for road segments with jams.

    (6) create_segments.py
        Create road segments from OpenStreetMap
        Uses osm_elements.geojson to create segments
        Outputs:
            inters_segments.geojson
            inter_and_non_int.geojson

    (7) extract_intersections.py
        Depends on extra_map variable
        Extracts intersection data from the extra_map
        Outputs:
            inters.pkl
            elements.geojson

    (7b) create_segments.py
        Create segments is extra_map exists. Different variables from before
        Create segments for extra_map

    (7c) add_map.py
        Outputs:
            inters_data.json
            non_inters_segments.geojson

    (8) join_segments_crash_concern.py
        Join segment data with the crash_concern data
        Opens up inters_segments.geojson
        Opens up non_inters_segments.geojson
        Remaps them into useful format
        Returns the combined segments and an indexing array that is used for faster lookups
        Outputs:
            ..._joined.json
            e.g. concern_joined.json
            e.g. crashes_joined.json

    (9) propagate_volume.py

    (10) TMC_scraping.parse_tmc.py

    (11) make_canon_dataset.py

## Train Model

    (1) Parses args

    (2) Loads in configs and sets some defaults if they are not present. This looks like it could easily cause bugs.

    (3) Read in the seg_data as set in config.

    (4) Various Data formatting

    (5) Initialize and Run

### Initialize and Run

    (1) Set parameters with set_params()
    cv = crossvalidation parameters.
        Defaults with 5 folds, 5 iterations, uses roc_auc, shuffles

    mp = model parameters

    mp['LogisticRegression'] = logistic regression parameters
        L1 + L2 regularization
        Chooses beta from a distribution
        Balanced class_weight

    mp['XGBClassifier'] = XGBoost parameters
        max_depth = list(range(3,7))
        min_child_weight between = list(range(1,5))
        learning_rate = ss.beta(a=2, b=15)

    perf_cutoff = 0.5

    (2) Only take the largest feature of sections going into an intersection

    (3) Create lagged crash data

    (4) initialize_and_run

    Create dataframe instance from Indata class
    Train and Test split on the dataframe class

    Create tuner instance from Tuner class
    Tune XG and LR

    Create Tester instance from Tester class
    Test the tuned models

    Choose best performing model and run fit on whole data set.

    Predict



