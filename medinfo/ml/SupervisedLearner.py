'''
Besides the regular pipelining, this new file allows starting from any
intermediate step.

Procedure for writing this module:
1. Make it usable for Lab Normality test (so assume the old naming organization)
2. More flexible for template naming


Assumption 1: Input is raw matrix
This module assumes generated raw matrix (TODO: use luigi).
Do not call function to Extract from SQL and Feature Engineering

Assumption 2: Naming rules

- project_folder (e.g. LabTestAnalysis/)
--- project_ml_folder (machine_learning/)
----- data set folder (e.g. data-Stanford-panel-10000-episodes/)
------- raw matrix (e.g. LABA1C-normality-matrix-raw.tab)
------- pat_split.csv
------- processed matrices (e.g. LABA1C-normality-matrix-processed.tab,
                                LABA1C-normality-train-matrix-processed.tab,
                                LABA1C-normality-evalu-matrix-processed.tab)
------- saved ml classifiers (LABA1C-normality-random-forest-model.pkl)
------- baseline_comparisons.csv, baseline_comparisons_train.csv
------- data alg folder (e.g. random-forest/)
--------- direct_comparisons.csv, direct_comparisons_train.csv

--- project_stats_folder


Trying to piecing together different function parts (reliably),
instead of realizing any specific functions.

TODO: Specific pipelines do not "override" this singleton class, but calls its function?
'''

# Name key functions that thing should have
#  Feature Matrix generation
#  Feature selection
#  Imputation
#  Different model learning with different hyperparam options
#  Evaluating quality of a model (generate result calculation)
#  Separate test set evaluation
#  Saving matrix, models, results to files
#
# - Write the application code file. but API ONLY!
#    Don't implement. Just write function definitions (so you know what goes in and what comes out)
#    "Return empty"
# - Write unit tests that each go after one piece of the application
#    (this should be simple looking. Because it mimics what your final driver/script will look like)
# - Run unit test -> no compiler errors, only value fails.
# - Implement application until test passes.

import LocalEnv
import os
import pickle

from medinfo.ml.FeatureSelector import FeatureSelector
import pandas as pd
pd.set_option('display.width', 3000)
pd.set_option('display.max_columns', 3000)
import numpy as np
from sklearn.model_selection import train_test_split as sklearn_train_test_split
from sklearn.externals import joblib
from sklearn.calibration import CalibratedClassifierCV

from medinfo.dataconversion.FeatureMatrixIO import FeatureMatrixIO
from medinfo.ml.SupervisedClassifier import SupervisedClassifier



'''
Templates
'''
raw_matrix_template = '%s-normality-matrix-raw.tab'
pat_split_filename = 'pat_split.csv'

processed_matrix_template = '%s-normality-matrix-processed.tab'
processed_matrix_train_template = '%s-normality-train-matrix-processed.tab'
processed_matrix_evalu_template = '%s-normality-test-matrix-processed.tab' # TODO: rename test-matrix to evalu-matrix in the pipeline

direct_comparisons_train_filename = 'direct_comparisons_train.csv'
direct_comparisons_evalu_filename = 'direct_comparisons.csv'

classifier_filename_template = '%s-normality-%s-model.pkl'

############# Util functions #############
'''
General functions for smaller tasks
'''
def split_rows(data_matrix, train_size=0.75, columnToSplitOn='pat_id', random_state=0):

    # from sklearn.model_selection import GroupShuffleSplit
    # print data_matrix.shape
    # train_inds, evalu_inds = next(
    #     GroupShuffleSplit(n_splits=2, test_size=1-train_size, random_state=random_state)
    #         .split(data_matrix, groups=data_matrix[columnToSplitOn])
    # )
    # print len(train_inds) + len(evalu_inds)
    #
    # data_matrix_train, data_matrix_evalu = data_matrix.iloc[train_inds], data_matrix.iloc[evalu_inds]
    #
    # pat_ids_train = data_matrix_train['pat_id'].values.tolist()
    # pat_ids_evalu = data_matrix_evalu['pat_id'].values.tolist()

    all_possible_ids = sorted(set(data_matrix[columnToSplitOn].values.tolist()))

    train_ids, test_ids = sklearn_train_test_split(all_possible_ids, test_size=1.-train_size, random_state=random_state)

    data_matrix_train = data_matrix[data_matrix[columnToSplitOn].isin(train_ids)].copy()
    # y_train = pd.DataFrame(train_matrix.pop(outcome_label))
    # X_train = train_matrix

    data_matrix_evalu = data_matrix[data_matrix[columnToSplitOn].isin(test_ids)].copy()
    # y_test = pd.DataFrame(test_matrix.pop(outcome_label))
    # X_test = test_matrix

    pat_ids_train = data_matrix_train['pat_id'].values.tolist()
    pat_ids_evalu = data_matrix_evalu['pat_id'].values.tolist()
    assert (set(pat_ids_train) & set(pat_ids_evalu)) == set([])

    assert data_matrix_train.shape[0] + data_matrix_evalu.shape[0] == data_matrix.shape[0]

    return data_matrix_train, data_matrix_evalu


def split_Xy(data_matrix, outcome_label):
    X = data_matrix.loc[:, data_matrix.columns != outcome_label].copy()
    y = data_matrix.loc[:, outcome_label].copy()
    return X, y

def get_algs():
    return SupervisedClassifier.SUPPORTED_ALGORITHMS
############# Util functions #############





############# Procedure functions #############

def load_raw_matrix(lab, dataset_folderpath):
    data_lab_folderpath = os.path.join(dataset_folderpath, lab)
    raw_matrix_filepath = os.path.join(data_lab_folderpath, raw_matrix_template % lab)
    fm_io = FeatureMatrixIO()

    # TODO: check if raw matrix exists
    raw_matrix = fm_io.read_file_to_data_frame(raw_matrix_filepath)
    return raw_matrix

def load_processed_matrix(lab, dataset_folderpath, type='full'):
    data_lab_folderpath = os.path.join(dataset_folderpath, lab)

    if type=='train':
        matrix_filepath = os.path.join(data_lab_folderpath, processed_matrix_train_template % lab)
    elif type=='evalu':
        matrix_filepath = os.path.join(data_lab_folderpath, processed_matrix_evalu_template % lab)
    else:
        matrix_filepath = os.path.join(data_lab_folderpath, processed_matrix_template % lab)

    fm_io = FeatureMatrixIO()

    # TODO: check if raw matrix exists
    if os.path.exists(matrix_filepath):
        matrix = fm_io.read_file_to_data_frame(matrix_filepath)
    else:
        matrix = fm_io.read_file_to_data_frame(matrix_filepath.replace('-test', '-evalu'))
    return matrix

def load_imputation_template(lab, dataset_folderpath, lab_type='panel'):
    data_lab_folderpath = os.path.join(dataset_folderpath, lab)
    imputations = pickle.load(open(data_lab_folderpath + '/' + "feat2imputed_dict.pkl"))

    if len(imputations) < 200: #
        '''
        only includes selected features
        '''
        return imputations

    if lab_type == 'panel':
        ylabel = 'all_components_normal'
    else:
        ylabel = 'component_normal'

    '''
    All raw matrix's columns are included. Have to extract final features from processed matrix
    '''
    fm_io = FeatureMatrixIO()
    df_processed = fm_io.read_file_to_data_frame(
        data_lab_folderpath + '/' + '%s-normality-matrix-processed.tab' % lab)
    df_processed.pop('pat_id')
    df_processed.pop(ylabel)  # TODO?!

    processed_columns_stanford = df_processed.columns.values.tolist()

    imputations_new = {}
    for i, col_selected in enumerate(processed_columns_stanford):
        imputations_new[col_selected] = (i, imputations[col_selected])
    return imputations_new

def load_ML_model(lab, alg, dataset_folderpath):
    data_lab_folderpath = os.path.join(dataset_folderpath, lab)
    return joblib.load(data_lab_folderpath + '/' + '%s-normality-%s-model.pkl' % (lab,alg))






'''
If do not want to use cached, just delete the file!
'''
def get_train_and_evalu_raw_matrices(lab, dataset_folderpath, random_state,
                                    train_size=0.75, columnToSplitOn='pat_id'):
    '''
    If train and eval exist, direct get from disk
    Avoided saving as 2 raw matrices, too much space!

    elif raw matrix exists, get from dist and split

    else, get from SQL

    Args:
        raw_matrix_filepath:
        random_state:
        use_cached:

    Returns:

    '''
    # raw_matrix_filepath = os.path.join(data_lab_folderpath, raw_matrix_template % lab)
    # fm_io = FeatureMatrixIO()
    #
    # # TODO: check if raw matrix exists
    # raw_matrix = fm_io.read_file_to_data_frame(raw_matrix_filepath)

    raw_matrix = get_raw_matrix(lab, dataset_folderpath)


    data_lab_folderpath = os.path.join(dataset_folderpath, lab)
    pat_split_filepath = os.path.join(data_lab_folderpath, pat_split_filename)

    '''
    Old pipeline style
    '''
    if os.path.exists(pat_split_filepath):
        pat_split_df = pd.read_csv(pat_split_filepath)
        pat_ids_train = pat_split_df[pat_split_df['in_train']==1]['pat_id'].values.tolist()
        raw_matrix_train = raw_matrix[raw_matrix['pat_id'].isin(pat_ids_train)]

        pat_ids_evalu = pat_split_df[pat_split_df['in_train']==0]['pat_id'].values.tolist()
        raw_matrix_evalu = raw_matrix[raw_matrix['pat_id'].isin(pat_ids_evalu)]

    else:
        # TODO: to be consistent to previous implementation
        raw_matrix['pat_id'] = raw_matrix['pat_id'].apply(lambda x: str(x))

        raw_matrix_train, raw_matrix_evalu = split_rows(raw_matrix,
                                                        train_size=train_size,
                                                        columnToSplitOn=columnToSplitOn,
                                                        random_state=random_state
                                                        )
        pat_ids_train = set(raw_matrix_train['pat_id'].values.tolist())

        pat_split_df = raw_matrix[['pat_id']].copy()
        pat_split_df['in_train'] = pat_split_df['pat_id'].apply(lambda x: 1 if x in pat_ids_train else 0)
        # pat_split_df.to_csv(pat_split_filepath, index=False)

    assert set(raw_matrix_train['pat_id'].values.tolist()) & set(raw_matrix_evalu['pat_id'].values.tolist()) == set([])
    assert raw_matrix_train.shape[0] + raw_matrix_evalu.shape[0] == raw_matrix.shape[0]

    return raw_matrix_train, raw_matrix_evalu


def get_train_and_evalu_processed_matrices(lab, dataset_folderpath, features, random_state):
    '''



    Args:
        lab:
        data_lab_folderpath:
        random_state:

    Returns:

    '''
    data_lab_folderpath = os.path.join(dataset_folderpath, lab)

    processed_matrix_train_filepath = os.path.join(data_lab_folderpath, processed_matrix_train_template % lab)
    processed_matrix_evalu_filepath = os.path.join(data_lab_folderpath, processed_matrix_evalu_template % lab)

    if os.path.exists(processed_matrix_train_filepath) and os.path.exists(processed_matrix_evalu_filepath):
        processed_matrix_train = pd.read_csv(processed_matrix_train_filepath, keep_default_na=False, sep='\t')
        processed_matrix_evalu = pd.read_csv(processed_matrix_evalu_filepath, keep_default_na=False, sep='\t')
        pass

    else:
        raw_matrix_train, raw_matrix_evalu = get_train_and_evalu_raw_matrices(lab, dataset_folderpath, random_state)
        assert raw_matrix_train.shape[0] > raw_matrix_evalu.shape[0]
        assert raw_matrix_train.shape[1] == raw_matrix_evalu.shape[1]
        '''
        
        '''

        processed_matrix_train, impute_template  = process_matrix(raw_matrix_train, features=features)
        processed_matrix_evalu, _ = process_matrix(raw_matrix_evalu, features=features, impute_template=impute_template)

        processed_matrix_train.to_csv(processed_matrix_train_filepath, sep='\t', index=False)
        processed_matrix_evalu.to_csv(processed_matrix_evalu_filepath, sep='\t', index=False)

    for feature in features['keep']:
        assert feature in processed_matrix_train.columns.values

        assert feature in processed_matrix_evalu.columns.values

    return processed_matrix_train, processed_matrix_evalu



def impute_features(matrix, strategy):

    impute_template = {}

    features_to_remove = {}

    for feature in matrix.columns.values:
        '''
        If all values are null, just remove the feature.
        Otherwise, imputation will fail (there's no mean value),
        and sklearn will ragequit.
        '''
        if matrix[feature].isnull().all():
            features_to_remove.append(feature)

        else:
            '''
            Only try to impute if some of the values are null.
            '''
            #TODO: other strategies
            if matrix[feature].dtype not in (int, long, float):
                print feature, matrix[feature].dtype
                continue

            imputed_value = matrix[feature].mean()
            impute_template[feature] = imputed_value

            matrix[feature].fillna(imputed_value, inplace=True)

    matrix = matrix.drop(features_to_remove, axis=1)
    # TODO: assert all existing features have impute values

    return matrix, impute_template



def select_features(matrix, features, random_state=0):
    select_params = features['select_params']
    fs = FeatureSelector(problem = select_params['selection_problem'],
                         algorithm = select_params['selection_algorithm'],
                         random_state = random_state
                         )

    X, y = split_Xy(matrix, features['ylabel'])
    fs.set_input_matrix(X, y)
    num_features_to_select = int(select_params['percent_features_to_select'] * len(matrix.columns.values))

    fs.select(k=num_features_to_select)

    feature_ranks = fs.compute_ranks()

    features_to_keep = []
    for i in range(len(feature_ranks)):
        if feature_ranks[i] <= num_features_to_select:
            # If in features_to_keep, pretend it wasn't eliminated.
            # self._eliminated_features.append(self._X_train.columns[i])
            features_to_keep.append(X.columns[i])

    return matrix[features_to_keep].copy()

def process_matrix(raw_matrix, features, impute_template=None):
    '''
    From raw matrix to processed matrix

    Processed matrix, column order:
        ylabel, numeric features, info columns

    If process_template (key: feature, val: imputed val) is provided:
        TODO

    else:
        (1) Remove specified feature (e.g. 'abnormal', 'num_components')
        (2) Select numeric features from the raw matrices
        (exclude y label and info features (to be removed before training),
        e.g. 'pat_id', 'order_time', )

    Args:
        lab:
        raw_matrix:
        features_dict:
        data_path:
        impute_template:

    Returns:

    '''

    '''
    Process matrix from scratch

    Column order: ylabel, info, numeric
    '''
    processing_matrix = raw_matrix.copy()


    '''
    Set aside info features 
    '''

    features_setaside = features['info']
    processed_matrix = processing_matrix[features_setaside].copy()
    processing_matrix = processing_matrix.drop(features_setaside, axis=1)

    '''
    Set aside ylabel
    '''
    ylabel_matrix = processing_matrix[[features['ylabel']]].copy()
    processing_matrix = processing_matrix.drop(features['ylabel'], axis=1)

    if impute_template is not None:
        '''
        Select and impute feature based on previous template
        '''
        columns_impute_ordered = [""] * len(impute_template.keys())

        for feature, ind_value_pair in impute_template.items():
            column_ind, impute_value = ind_value_pair
            processing_matrix[feature] = processing_matrix[feature].fillna(impute_value)

            columns_impute_ordered[column_ind] = feature

        # if 'abnormal_panel' not in processing_matrix.columns.values.tolist(): #TODO: delete in the future
        #     processing_matrix['abnormal_panel'] = processing_matrix['all_components_normal'].apply(lambda x:1.-x)

        processing_matrix = processing_matrix[columns_impute_ordered]
        # TODO: header info like done by fm_io?

        # processing_matrix = pd.concat([ylabel_matrix, processing_matrix], axis=1)

    else:
        '''
        Now processing_matrix only contains numeric features
        '''


        '''
        Remove features
        '''
        processing_matrix = processing_matrix.drop(features['remove'], axis=1)


        # TODO: test: only numeric features left

        '''
        Impute
        
        TODO: alert if 'keep' are all NaN..
        
        TODO: if y-label has missing value?
        '''

        processing_matrix, impute_template = impute_features(processing_matrix, strategy="mean")


        # TODO: keep order?

        '''
        Keep features
        '''
        keep_features = features['keep']
        processed_matrix = pd.concat([processed_matrix, processing_matrix[keep_features].copy()], axis=1) # or concat?
        processing_matrix = processing_matrix.drop(keep_features, axis=1)


        '''
        Select features
        
        Needs y-label when selecting.
        However, y-label will not be returned from select_features()
        '''
        processing_matrix = pd.concat([ylabel_matrix, processing_matrix], axis=1)

        processing_matrix = select_features(processing_matrix,
                                            features=features)


        '''
        Record the order of the feature in the numeric matrix, 
        as the dictionary impute_template does not keep order
        '''

        for key, val in impute_template.items():
            if key not in processing_matrix.columns and key not in features['keep']:
                impute_template.pop(key)
            elif key in features['keep']:
                '''
                features['keep'] is not in "pro"-selected features, since it is "pre"-selected
                '''
                feature_ind = len(processing_matrix.columns.tolist())
                impute_template[key] = (feature_ind, impute_template[key])
            else:
                feature_ind = processing_matrix.columns.tolist().index(key)
                impute_template[key] = (feature_ind, impute_template[key])
        # processed_matrix = pd.merge(processed_matrix, processing_matrix)

        # TODO: save impute_template to disk


    processed_matrix = pd.concat([ylabel_matrix, processing_matrix, processed_matrix], axis=1)

    return processed_matrix, impute_template

def train_ml_model(X_train, y_train, alg, groups, output_folderpath, random_state):
    hyperparams = {}
    hyperparams['algorithm'] = alg

    ml_classifier = SupervisedClassifier(classes=[0,1], hyperparams=hyperparams)


    status = ml_classifier.train(X_train, y_train, groups=groups)
    return ml_classifier

def predict(X, y, ml_classifier, output_filepath):
    ''
    y_pred_proba = ml_classifier.predict_probability(X)[:,1]
    y_true = y.values

    # actual_reindex = y.reset_index(drop=True)
    # predict_reindex = y_pred_proba.reset_index(drop=True)
    direct_comparisons = pd.DataFrame({'actual':y_true, 'predict':y_pred_proba})
        # actual_reindex.join(predict_reindex)
    # direct_comparisons.columns = ['actual', 'predict']
    direct_comparisons.to_csv(output_filepath, index=False)

def standard_pipeline(lab, algs, learner_params, dataset_folderpath, random_state):
    '''
    This pipelining procedure is consistent to the previous SupervisedLearningPipeline.py

    Args:
        lab:
        data_lab_folderpath:
        random_state:

    Returns:
        None, just write direct comparisons between y_true and y_pred_proba
    '''

    '''
    Feature selection
    Here process_template is a dictionary w/ {feature: (ind, imputed value)}

    Things to test:
    Number of columns left.
    No missing values. 
    Number of episodes for each patient does not change. 
    '''

    processed_matrix_train, processed_matrix_evalu = \
        get_train_and_evalu_processed_matrices(lab=lab,
                                               features=learner_params['features'],
                                               dataset_folderpath=dataset_folderpath,
                                               random_state=random_state)

    '''
    Things to test: numeric only
    '''

    '''
    Things to test:
    No missing features
    No overlapping features
    '''
    X_train, y_train = split_Xy(data_matrix=processed_matrix_train,
                                   outcome_label=learner_params['features']['ylabel'])
    X_evalu, y_evalu = split_Xy(data_matrix=processed_matrix_evalu,
                                   outcome_label=learner_params['features']['ylabel'])
    X_evalu.pop('pat_id')
    '''
    Training

    Things to test: numeric only:
    Before and after training, the model is different
    '''
    ml_classifiers = []
    for alg in algs:
        '''
        Training
        '''
        data_alg_folderpath = os.path.join(data_lab_folderpath, alg)
        if not os.path.exists(data_alg_folderpath):
            os.mkdir(data_alg_folderpath)

        direct_comparisons_evalu_filepath = os.path.join(data_alg_folderpath, direct_comparisons_train_filename)
        if os.path.exists(direct_comparisons_evalu_filepath):
            continue


        # TODO: in the future, even the CV step requires splitByPatId, so carry forward this column?
        # TODO: or load from disk
        ml_classifier_filename = classifier_filename_template % (lab, alg)
        ml_classifier_filepath = os.path.join(data_lab_folderpath, ml_classifier_filename)

        if os.path.exists(ml_classifier_filepath):
            ml_classifier = joblib.load(ml_classifier_filepath)
        else:

            patIds_train = X_train.pop('pat_id').values.tolist()
            ml_classifier = train_ml_model(X_train=X_train,
                                              y_train=y_train,
                                              alg=alg,
                                           groups=patIds_train,
                                              output_folderpath=data_alg_folderpath,
                                           random_state=random_state
                                            )  # ?

            joblib.dump(ml_classifier, ml_classifier_filepath)

        '''
        Predicting train set results (overfit)
        '''
        # predict(X=X_train,
        #            y=y_train,
        #            ml_classifier=ml_classifier,
        #            output_folderpath=data_alg_folderpath)

        '''
        Predicting evalu set feature selection
        '''
        predict(X=X_evalu,
                y=y_evalu,
                ml_classifier=ml_classifier,
                output_filepath=direct_comparisons_evalu_filepath)

    # TODO here: make sure process_matrix works right
    # processed_matrix_full_eval, _ = SL.process_matrix(lab=lab,
    #                                      raw_matrix=raw_matrix_eval,
    #                                      features_dict=features_dict,
    #                                      data_folder=data_folder,
    #                                     process_template=process_template)
    # processed_matrix_eval = processed_matrix_full_eval.drop(info_features+leak_features, axis=1)
    # X_eval, y_eval = SL.split_Xy(data_matrix=processed_matrix_eval,
    #                                outcome_label=outcome_label,
    #                              random_state=random_state)





if __name__ == '__main__':
    pass

