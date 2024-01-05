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

from typing import List

import pytest
from argilla.client.feedback.dataset.local.dataset import FeedbackDataset
from argilla.client.feedback.integrations.sentencetransformers import SentenceTransformersExtractor
from argilla.client.feedback.schemas.fields import TextField
from argilla.client.feedback.schemas.questions import TextQuestion
from argilla.client.feedback.schemas.records import FeedbackRecord


@pytest.fixture
def records() -> List[FeedbackRecord]:
    return [
        FeedbackRecord(fields={"field_1": "This is a test", "field_2": "This is a test"}),
        FeedbackRecord(
            fields={
                "field_1": "This is a test",
            }
        ),
        FeedbackRecord(
            fields={"field_1": "This is a test", "field_2": "This is a test"},
        ),
    ]


@pytest.fixture
def st_extractor() -> SentenceTransformersExtractor:
    return SentenceTransformersExtractor()


@pytest.fixture
def dataset() -> FeedbackDataset:
    ds = FeedbackDataset(
        fields=[
            TextField(name="field_1"),
            TextField(name="field_2", required=False),
        ],
        questions=[
            TextQuestion(name="question_1"),
        ],
    )
    return ds


def test_update_dataset(
    st_extractor: SentenceTransformersExtractor,
    dataset: FeedbackDataset,
    records: List[FeedbackRecord],
):
    dataset.add_records(records)
    dataset = st_extractor.update_dataset(dataset, fields=["field_1"], include_records=False)
    assert dataset.vector_settings_by_name("field_1")
    assert not dataset.vector_settings_by_name("field_2")
    assert not dataset.records[0].vectors
    dataset = st_extractor.update_dataset(dataset, fields=["field_2"], include_records=False)
    dataset = st_extractor.update_dataset(dataset, include_records=True, fields=["field_1"])
    assert "field_1" in dataset.records[0].vectors
    assert "field_2" not in dataset.records[0].vectors
    dataset = st_extractor.update_dataset(dataset, include_records=True, fields=["field_2"])
    assert "field_1" in dataset.records[0].vectors
    assert "field_2" in dataset.records[0].vectors
    assert "field_2" not in dataset.records[1].vectors


def test_update_records(st_extractor: SentenceTransformersExtractor, records: List[FeedbackRecord]):
    records = st_extractor.update_records(records, fields=["field_1"])
    assert "field_1" in records[0].vectors
    assert "field_2" not in records[0].vectors
    records = st_extractor.update_records(records, fields=["field_2"])
    assert "field_1" in records[0].vectors
    assert "field_2" in records[0].vectors
