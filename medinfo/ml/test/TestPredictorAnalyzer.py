#!/usr/bin/python
"""
Test suite for PredictorAnalyzer.
"""

import filecmp
import os
from pandas.util.testing import assert_frame_equal
from pandas import DataFrame
import unittest

from LocalEnv import TEST_RUNNER_VERBOSITY
from medinfo.common.test.Util import make_test_suite, MedInfoTestCase
from medinfo.ml.Predictor import Predictor
from medinfo.ml.PredictorAnalyzer import PredictorAnalyzer
from PredictorAnalyzerTestData import MANUAL_PREDICTION_TEST_CASE

class ListPredictor(Predictor):
    # Fake predictor meant purely for testing. It accepts a list of predictions
    # and just cycles through those predictions.
    def __init__(self, predictions):
        self._index = 0
        self._predictions = predictions
        self._num_predictions = len(self._predictions)

    def __repr__(self):
        return 'ListPredictor(%s)' % self._predictions.values

    __str__ = __repr__

    def predict(self, X):
        y_predicted = list()
        for row in X.iterrows():
            prediction = self._predictions[self._index]
            y_predicted.append(prediction)
            self._index = (self._index + 1) % self._num_predictions

        return DataFrame({'y_predicted': y_predicted})

class TestPredictorAnalyzer(MedInfoTestCase):
    def setUp(self):
        # Fetch data.
        X_test = MANUAL_PREDICTION_TEST_CASE['X']
        y_test = MANUAL_PREDICTION_TEST_CASE['y_true']
        y_predicted = MANUAL_PREDICTION_TEST_CASE['y_predicted']

        # Initialize predictor and analyzer.
        self._predictor = ListPredictor(y_predicted['predictions'])
        self._analyzer = PredictorAnalyzer(self._predictor, X_test, y_test)

    def tearDown(self):
        # Clean up the actual report file.
        try:
            test_dir = os.path.dirname(os.path.abspath(__file__))
            actual_report_name = 'actual-list-predictor.report'
            actual_report_path = '/'.join([test_dir, actual_report_name])
            os.remove(actual_report_path)
        except OSError:
            pass

    def test_score_accuracy(self):
        # Compute accuracy.
        expected_accuracy = MANUAL_PREDICTION_TEST_CASE['accuracy']
        actual_accuracy = self._analyzer.score(metric=PredictorAnalyzer.ACCURACY_SCORE)

        # Assert values are correct.
        self.assertEqual(expected_accuracy, actual_accuracy)

    def test_build_report(self):
        # Build report.
        expected_report = MANUAL_PREDICTION_TEST_CASE['report']
        actual_report = self._analyzer.build_report()

        # Assert values are correct.
        assert_frame_equal(expected_report, actual_report)

        # Build paths for expected and actual report.
        test_dir = os.path.dirname(os.path.abspath(__file__))
        expected_report_name = 'expected-list-predictor.report'
        actual_report_name = 'actual-list-predictor.report'
        expected_report_path = '/'.join([test_dir, expected_report_name])
        actual_report_path = '/'.join([test_dir, actual_report_name])

        # Write the report.

        self._analyzer.write_report(actual_report, actual_report_path)

        # Assert files equal.
        self.assertTrue(filecmp.cmp(expected_report_path, actual_report_path))

if __name__=='__main__':
    suite = make_test_suite(TestPredictorAnalyzer)
    unittest.TextTestRunner(verbosity=TEST_RUNNER_VERBOSITY).run(suite)