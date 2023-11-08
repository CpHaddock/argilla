#  Copyright 2021-present, the Recognai S.L. team.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""This module contains metrics to compare Annotator's suggestions vs responses. """

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Tuple, Union

import numpy as np
from pydantic import BaseModel

from argilla.client.feedback.schemas import (
    LabelQuestion,
    MultiLabelQuestion,
    RankingQuestion,
    RatingQuestion,
    TextQuestion,
)
from argilla.utils.dependency import requires_dependencies

if TYPE_CHECKING:
    from argilla.client.feedback.dataset import FeedbackDataset

import evaluate
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    multilabel_confusion_matrix,
    precision_score,
    recall_score,
)

# Type aliases
Responses = List[Union[float, int, str]]
Suggestions = Responses


class AnnotatorMetric:
    def __init__(self, dataset: "FeedbackDataset", question_name: str) -> None:
        self._dataset = dataset
        self._question_name = question_name
        self._question_type = type(self._dataset.question_by_name(question_name))
        if self._question_type in (MultiLabelQuestion, RankingQuestion):
            raise NotImplementedError(f"No metrics are defined currently for {self._question_type.__name__}")
        self._allowed_metrics = METRICS_PER_QUESTION[self._question_type]

    def _prepare_responses_and_suggestions(self) -> Tuple[Dict[int, Responses], Suggestions]:
        hf_dataset = self._dataset.format_as("datasets")
        # TODO(plaguss): We should expose this functionality more easily for a FeedbackDataset.
        # Create a dict of responses per user:
        responses_per_user = defaultdict(list)
        if self._question_type != RankingQuestion:
            for responses_ in hf_dataset[self._question_name]:
                for response in responses_:
                    user_id = response["user_id"]
                    if user_id is None:
                        raise NotImplementedError(
                            "In order to use this functionality the records need to be assigned to a user."
                        )
                    responses_per_user[user_id].append(response["value"])
        else:
            for responses_ in hf_dataset[self._question_name]:
                for response in responses_:
                    user_id = response["user_id"]
                    if user_id is None:
                        raise NotImplementedError(
                            "In order to use this functionality the records need to be assigned to a user."
                        )
                    responses_per_user[user_id].append(response["value"]["value"])

        suggestions = hf_dataset[f"{self._question_name}-suggestion"]
        if self._question_type == RankingQuestion:
            suggestions = [suggestion["value"] for suggestion in suggestions]
        # TODO(plaguss): Check there are suggestions for every response.

        return responses_per_user, suggestions

    def compute(self, metric_names: Union[str, List[str]], **kwargs) -> float:
        if isinstance(metric_names, str):
            metric_names = [metric_names]

        metric_classes = []
        for metric_name in metric_names:
            if metric_name not in self._allowed_metrics:
                raise ValueError(
                    f"Metric {metric} not allowed for question {self._question_name}, choose one from: {list(self._allowed_metrics.keys())}."
                )
            metric_classes.append((metric_name, self._allowed_metrics[metric_name]))

        responses_per_user, suggestions = self._prepare_responses_and_suggestions()
        # TODO(plaguss): check all the metrics are available for the question type
        metrics = defaultdict(list)
        for user_id, responses in responses_per_user.items():
            for metric_name, metric_cls in metric_classes:
                metric = metric_cls(responses=responses, suggestions=suggestions)
                result = metric.compute(**kwargs)
                metrics[user_id].append(AnnotatorMetricResult(metric_name=metric_name, result=result))

        return dict(metrics)


class AnnotatorMetricResult(BaseModel):
    metric_name: str
    result: Union[float, Dict[str, float], pd.DataFrame]

    class Config:
        arbitrary_types_allowed = True


class AnnotatorMetricBase(ABC):
    def __init__(self, responses=None, suggestions=None) -> None:
        self._responses = responses
        self._suggestions = suggestions

    def compute(self, **kwargs):
        responses, suggestions = self._pre_process(self._responses, self._suggestions)
        result = self._compute(responses, suggestions, **kwargs)
        return self._post_process(result)

    def _pre_process(self, responses, suggestions) -> Any:
        return responses, suggestions

    def _post_process(self, result: Any) -> Any:
        return result

    @abstractmethod
    def _compute(self, responses, suggestions, **kwargs):
        pass


def is_multiclass(data) -> bool:
    return len(np.unique(data)) > 2


class AccuracyMetric(AnnotatorMetricBase):
    def _compute(self, responses, suggestions, **kwargs):
        return accuracy_score(responses, suggestions, **kwargs)


class F1ScoreMetric(AnnotatorMetricBase):
    def _compute(self, responses, suggestions, **kwargs):
        if is_multiclass(responses) or is_multiclass(suggestions):
            if not kwargs.get("average"):
                kwargs.update({"average": "macro"})
        return f1_score(responses, suggestions, **kwargs)


class PrecisionMetric(AnnotatorMetricBase):
    def _compute(self, responses, suggestions, **kwargs):
        if is_multiclass(responses) or is_multiclass(suggestions):
            if not kwargs.get("average"):
                kwargs.update({"average": "macro"})
        return precision_score(responses, suggestions, **kwargs)


class RecallMetric(AnnotatorMetricBase):
    def _compute(self, responses, suggestions, **kwargs):
        if is_multiclass(responses) or is_multiclass(suggestions):
            if not kwargs.get("average"):
                kwargs.update({"average": "macro"})
        return recall_score(responses, suggestions, **kwargs)


class ConfusionMatrixMetric(AnnotatorMetricBase):
    def _compute(self, responses, suggestions, **kwargs):
        if is_multiclass(responses) or is_multiclass(suggestions):
            return multilabel_confusion_matrix(responses, suggestions, **kwargs)
        return confusion_matrix(responses, suggestions, **kwargs)


class CorrelationCoefficientMetric(AnnotatorMetricBase):
    def _compute(self, responses, suggestions, kind: Literal["pearson", "spearman", "kendall"] = "spearman", **kwargs):
        return (
            pd.DataFrame({"responses": responses, "suggestions": suggestions})
            .corr(method=kind)["responses"]
            .loc["suggestions"]
        )


@requires_dependencies("evaluate")
class GLEUMetric(AnnotatorMetricBase):
    # https://huggingface.co/spaces/evaluate-metric/google_bleu
    def _pre_process(self, responses, suggestions) -> Any:
        return responses, [[suggestion] for suggestion in suggestions]

    def _compute(self, responses: List[str], suggestions: List[str], **kwargs):
        gleu = evaluate.load("google_bleu")
        return gleu.compute(predictions=responses, references=suggestions, **kwargs)

    def _post_process(self, result: Any) -> Any:
        return result["google_bleu"]


class ROUGEMetric(AnnotatorMetricBase):
    # https://huggingface.co/spaces/evaluate-metric/rouge
    def _compute(self, responses: List[str], suggestions: List[str], **kwargs):
        rouge = evaluate.load("rouge")
        return rouge.compute(predictions=responses, references=suggestions, **kwargs)


METRICS_PER_QUESTION = {
    LabelQuestion: {
        "accuracy": AccuracyMetric,
        "f1-score": F1ScoreMetric,
        "precision": PrecisionMetric,
        "recall": RecallMetric,
        "confusion-matrix": ConfusionMatrixMetric,
    },
    # TODO(plaguss): Currently sklearn doesn't support any metrics for multiclass-multioutput
    # like the ones we offer for MultiLabel by default. We can either
    # restrict the type of MultiLabelQuestion so we can compute
    # for either multilabel or multiclass, or we have to define those metrics ourselves (or a use
    # a different library)
    MultiLabelQuestion: {
        "accuracy": AccuracyMetric,
    },
    RatingQuestion: {
        "accuracy": AccuracyMetric,
        "f1-score": F1ScoreMetric,
        "precision": PrecisionMetric,
        "recall": RecallMetric,
        "confusion-matrix": ConfusionMatrixMetric,
        "spearman-r": CorrelationCoefficientMetric,
    },
    # The following metric may work if the data os preprocessed
    # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.somersd.html.
    # Otherwise we have the same problem that appears with MultiLabelQuestion
    RankingQuestion: {
        "accuracy": AccuracyMetric,
    },
    TextQuestion: {
        "gleu": GLEUMetric,
        "rouge": ROUGEMetric,
    },
}
