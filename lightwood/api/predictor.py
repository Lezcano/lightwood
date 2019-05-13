import logging
import traceback

import dill
from sklearn.metrics import accuracy_score
from sklearn.metrics import explained_variance_score

from lightwood.api.data_source import DataSource
from lightwood.data_schemas.definition import definition_schema
from lightwood.mixers.sk_learn.sk_learn import SkLearnMixer


class Predictor:

    def __init__(self, definition=None, load_from_path=None):
        """
        Start a predictor pass the

        :param definition: a predictor definition object (can be a dictionary or a PredictorDefinition object)
        :param load_from_path: The path to load the predictor from
        :type definition: dictionary
        """

        if load_from_path is not None:
            pickle_in = open(load_from_path, "rb")
            self_dict = dill.load(pickle_in)
            pickle_in.close()
            self.__dict__ = self_dict
            return

        try:
            definition_schema.validate(definition)
        except:
            error = traceback.format_exc(1)
            raise ValueError('[BAD DEFINITION] argument has errors: {err}'.format(err=error))

        self.definition = definition
        self._encoders = None
        self._mixer = None
        self._encoded_cache = None
        self._Predictions = None

    def learn(self, from_data, test_data=None, validation_data=None):
        """
        Train and save a model (you can use this to retrain model from data)

        :param from_data:
        :param test_data:
        :param validation_data:
        :return:
        """

        from_data_ds = DataSource(from_data, self.definition)
        if test_data:
            test_data_ds = DataSource(test_data, self.definition)
        else:
            test_data_ds = None

        mixer = SkLearnMixer(
            input_column_names=[f['name'] for f in self.definition['input_features']],
            output_column_names=[f['name'] for f in self.definition['output_features']])

        for i, mix_i in enumerate(mixer.iter_fit(from_data_ds)):
            logging.info('training iteration {iter_i}'.format(iter_i=i))

        self._mixer = mixer
        self._encoders = from_data_ds.encoders
        self._encoded_cache = from_data_ds.encoded_cache
        self._Predictions = mixer.output_predictions

    def predict(self, when_data):
        """
        Predict given when conditions
        :param when_data: a dataframe
        :return: a complete dataframe
        """

        when_data_ds = DataSource(when_data, self.definition)
        when_data_ds.encoders = self._encoders

        return self._mixer.predict(when_data_ds)

    def accuracy(self, from_data):
        """
        calculates the accuracy of the model
        :param from_data:a dataframe
        :return accuracies: dictionaries of accuracies
        """
        if self._mixer is None:
            logging.log.error("Please train the model before calculating accuracy")
        from_data_ds = DataSource(from_data, self.definition)
        predictions = self._mixer.predict(from_data_ds)
        accuracies = {}
        for output_column in self._mixer.output_column_names:
            column_type = from_data_ds.get_column_config(output_column)['type']
            if column_type == 'categorical':
                accuracies[output_column] = accuracy_score(from_data_ds.get_column_original_data(output_column),
                                                            predictions[output_column]["Actual Predictions"])
            elif column_type == 'numeric':
                accuracies[output_column] = 0
            else:
                accuracies[output_column] = None

        return {'accuracies': accuracies}

    def accuracy_of_columns(self, target_columns):
        """
        calculates the accuracy of the model
        :param target_columns:a dataframe
        :return accuracies: dictionaries of accuracies
        """
        if self._mixer is None:
            logging.log.error("Please train the model before calculating accuracy")
        accuracies = {}
        for column in target_columns:
            y_true = list(self._encoded_cache[column].numpy())
            y_pred = list(self._Predictions[column]['Encoded Predictions'])
            accuracies[column] = explained_variance_score(y_true, y_pred, multioutput='uniform_average')

        return {'accuracies': accuracies}

    def save(self, path_to):
        """
        save trained model to a file
        :param path_to: full path of file, where we store results
        :return:
        """
        f = open(path_to, 'wb')
        dill.dump(self.__dict__, f)
        f.close()


# only run the test if this file is called from debugger
if __name__ == "__main__":
    # GENERATE DATA
    ###############
    import pandas
    import random

    config = {
        'name': 'test',
        'input_features': [
            {
                'name': 'x',
                'type': 'numeric',
                'encoder_path': 'lightwood.encoders.numeric.numeric'
            },
            {
                'name': 'y',
                'type': 'numeric',
                # 'encoder_path': 'lightwood.encoders.numeric.numeric'
            }
        ],

        'output_features': [
            {
                'name': 'z',
                'type': 'numeric',
                # 'encoder_path': 'lightwood.encoders.categorical.categorical'
            }
        ]
    }

    data = {'x': [i for i in range(10)], 'y': [random.randint(i, i + 20) for i in range(10)]}
    nums = [data['x'][i] * data['y'][i] for i in range(10)]
    data['z'] = [data['x'][i] + data['y'][i] + i for i in range(10)]
    data_frame = pandas.DataFrame(data)

    ####################
    predictor = Predictor(definition=config)
    predictor.learn(from_data=data_frame)
    print(predictor.predict(when_data=pandas.DataFrame({'x': [6], 'y': [12]})))

    predictor2 = Predictor(load_from_path='tmp/ok.pkl')
    print(predictor2.predict(when_data=pandas.DataFrame({'x': [6, 2, 3], 'y': [12, 3, 4]})))
    print(predictor2.accuracy_of_columns(target_columns=['z']))
