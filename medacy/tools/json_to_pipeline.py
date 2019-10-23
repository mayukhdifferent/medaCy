import json

import sklearn_crfsuite

from medacy.pipeline_components.metamap.metamap import MetaMap
from medacy.pipeline_components.metamap.metamap_component import MetaMapComponent
from medacy.pipeline_components.feature_extracters.discrete_feature_extractor import FeatureExtractor
from medacy.pipeline_components.feature_overlayers.gold_annotator_component import GoldAnnotatorComponent
from medacy.pipeline_components.learners.bilstm_crf_learner import BiLstmCrfLearner
from medacy.pipeline_components.tokenizers.clinical_tokenizer import ClinicalTokenizer
from medacy.pipeline_components.tokenizers.systematic_review_tokenizer import SystematicReviewTokenizer
from medacy.pipelines.base.base_pipeline import BasePipeline


required_keys = [
    'learner',
    'tokenizer',
    'entities',
    'spacy_pipeline',
    'spacy_features',
    'window_size',
]


def json_to_pipeline(json_path):
    """
    Constructs a custom pipeline from a json file

    The json must have the following keys:

    'learner': 'CRF' or 'BiLSTM'
        if 'learner' is 'BiLSTM', two additional keys are required:
            'cuda_device': the GPU to use
            'word_embeddings': path to the word embeddings file
    'tokenizer': 'clinical' or 'systematic_review'
    'entities': a list of strings
    'spacy_pipeline': the spaCy model to use
    'spacy_features': a list of features that exist as spaCy token annotations
    'window_size': the number of words +/- the target word whose features should be used along with the target word

    The following key is optional:
    'metamap': the path to the MetaMap binary; MetaMap will only be used if this key is present

    :param json_path: the path to the json file
    :return: a custom pipeline class
    """

    with open(json_path, 'rb') as f:
        input_json = json.load(f)

    for key in required_keys:
        if key not in input_json.keys():
            raise ValueError(f"Required key '{key}' was not found in the json file.")

    class CustomPipeline(BasePipeline):
        def __init__(self):
            super().__init__(
                "custom pipeline",
                spacy_pipeline=input_json['spacy_pipeline']
            )

            self.entities = input_json['entities']

            self.spacy_pipeline.tokenizer = self.get_tokenizer()

            self.add_component(GoldAnnotatorComponent, self.entities)

            if 'metamap' in input_json.keys():
                metamap = MetaMap(input_json['metamap'])
                self.add_component(MetaMapComponent, metamap)

        def get_tokenizer(self):
            tokenizers = {
                'clinical': ClinicalTokenizer,
                'systematic_review': SystematicReviewTokenizer
            }

            SelectedTokenizer = tokenizers[input_json['tokenizer']]

            return SelectedTokenizer(self.spacy_pipeline).tokenizer

        def get_learner(self):
            learner_selection = input_json['learner']

            if learner_selection == 'CRF':
                return ("CRF_l2sgd",
                    sklearn_crfsuite.CRF(
                        algorithm='l2sgd',
                        c2=0.1,
                        max_iterations=100,
                        all_possible_transitions=True
                    )
                )
            if learner_selection == 'BiLSTM':
                for k in ['word_embeddings', 'cuda_device']:
                    if k not in input_json.keys():
                        raise ValueError(f"'{k}' must be specified when the learner is BiLSTM")
                return'BiLSTM+CRF', BiLstmCrfLearner(input_json['word_embeddings'], input_json['cuda_device'])
            else:
                raise ValueError(f"'learner' must be 'CRF' or 'BiLSTM")

        def get_feature_extractor(self):
            return FeatureExtractor(
                window_size=input_json['window_size'],
                spacy_features=input_json['spacy_features']
            )

    return CustomPipeline
