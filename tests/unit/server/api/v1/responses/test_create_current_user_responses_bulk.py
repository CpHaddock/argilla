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

from datetime import datetime
from unittest.mock import call
from uuid import UUID, uuid4

import pytest
from argilla.server.constants import API_KEY_HEADER_NAME
from argilla.server.enums import ResponseStatus
from argilla.server.models import Response, User
from argilla.server.search_engine import SearchEngine
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    AnnotatorFactory,
    DatasetFactory,
    RatingQuestionFactory,
    RecordFactory,
    ResponseFactory,
    WorkspaceUserFactory,
)


@pytest.mark.asyncio
class TestCreateCurrentUserResponsesBulk:
    def url(self) -> str:
        return f"/api/v1/me/responses/bulk"

    def bulk_max_items(self) -> int:
        return 100

    async def test_multiple_responses(
        self, async_client: AsyncClient, db: AsyncSession, mock_search_engine: SearchEngine
    ):
        dataset = await DatasetFactory.create()
        await RatingQuestionFactory.create(name="prompt-quality", required=True, dataset=dataset)

        annotator = await AnnotatorFactory.create()
        await WorkspaceUserFactory.create(user_id=annotator.id, workspace_id=dataset.workspace.id)

        records = await RecordFactory.create_batch(3, dataset=dataset)

        other_dataset = await DatasetFactory.create()
        other_record = await RecordFactory.create(dataset=other_dataset)

        response_to_create_json = {
            "values": {"prompt-quality": {"value": 5}},
            "status": ResponseStatus.submitted,
            "record_id": str(records[0].id),
        }

        response_to_update = await ResponseFactory.create(
            status=ResponseStatus.draft,
            values={"prompt-quality": {"value": 1}},
            record=records[1],
            user=annotator,
        )

        response_to_update_json = {
            "values": {"prompt-quality": {"value": 10}},
            "status": ResponseStatus.submitted,
            "record_id": str(response_to_update.record_id),
        }

        invalid_response_json = {
            "values": {"non-existent-question": {"value": 10}},
            "status": ResponseStatus.submitted,
            "record_id": str(records[2].id),
        }

        unauthorized_response_json = {
            "status": ResponseStatus.draft,
            "record_id": str(other_record.id),
        }

        resp = await async_client.post(
            self.url(),
            headers={API_KEY_HEADER_NAME: annotator.api_key},
            json={
                "items": [
                    response_to_create_json,
                    response_to_update_json,
                    invalid_response_json,
                    unauthorized_response_json,
                ],
            },
        )

        assert resp.status_code == 200

        resp_json = resp.json()
        response_to_create_id = UUID(resp_json["items"][0]["item"]["id"])
        assert resp_json == {
            "items": [
                {
                    "item": {
                        "id": str(response_to_create_id),
                        "values": {"prompt-quality": {"value": 5}},
                        "status": ResponseStatus.submitted.value,
                        "record_id": str(records[0].id),
                        "user_id": str(annotator.id),
                        "inserted_at": datetime.fromisoformat(resp_json["items"][0]["item"]["inserted_at"]).isoformat(),
                        "updated_at": datetime.fromisoformat(resp_json["items"][0]["item"]["updated_at"]).isoformat(),
                    },
                    "error": None,
                },
                {
                    "item": {
                        "id": str(response_to_update.id),
                        "values": {"prompt-quality": {"value": 10}},
                        "status": ResponseStatus.submitted.value,
                        "record_id": str(records[1].id),
                        "user_id": str(annotator.id),
                        "inserted_at": datetime.fromisoformat(resp_json["items"][1]["item"]["inserted_at"]).isoformat(),
                        "updated_at": datetime.fromisoformat(resp_json["items"][1]["item"]["updated_at"]).isoformat(),
                    },
                    "error": None,
                },
                {
                    "item": None,
                    "error": {
                        "detail": "missing question with name=prompt-quality",
                    },
                },
                {
                    "item": None,
                    "error": {
                        "detail": "argilla.api.errors::ForbiddenOperationError(detail=Operation not allowed)",
                    },
                },
            ],
        }

        assert (await db.execute(select(func.count(Response.id)))).scalar() == 2

        response_to_create = (await db.execute(select(Response).filter_by(id=response_to_create_id))).scalar_one()
        await db.refresh(response_to_update)
        expected_calls = [
            call(response_to_create),
            call(response_to_update),
        ]
        mock_search_engine.update_record_response.assert_has_calls(expected_calls)

    async def test_response_to_create(
        self,
        async_client: AsyncClient,
        db: AsyncSession,
        mock_search_engine: SearchEngine,
        owner: User,
        owner_auth_header: dict,
    ):
        dataset = await DatasetFactory.create()
        await RatingQuestionFactory.create(name="prompt-quality", required=True, dataset=dataset)

        record = await RecordFactory.create(dataset=dataset)

        resp = await async_client.post(
            self.url(),
            headers=owner_auth_header,
            json={
                "items": [
                    {
                        "values": {"prompt-quality": {"value": 10}},
                        "status": ResponseStatus.submitted,
                        "record_id": str(record.id),
                    },
                ],
            },
        )

        assert resp.status_code == 200

        resp_json = resp.json()
        response_id = UUID(resp_json["items"][0]["item"]["id"])
        assert resp_json == {
            "items": [
                {
                    "item": {
                        "id": str(response_id),
                        "values": {"prompt-quality": {"value": 10}},
                        "status": ResponseStatus.submitted.value,
                        "record_id": str(record.id),
                        "user_id": str(owner.id),
                        "inserted_at": datetime.fromisoformat(resp_json["items"][0]["item"]["inserted_at"]).isoformat(),
                        "updated_at": datetime.fromisoformat(resp_json["items"][0]["item"]["updated_at"]).isoformat(),
                    },
                    "error": None,
                },
            ],
        }

        assert (await db.execute(select(func.count(Response.id)))).scalar() == 1

        response = (await db.execute(select(Response).filter_by(id=response_id))).scalar_one()
        mock_search_engine.update_record_response.assert_called_once_with(response)

    async def test_response_to_create_with_non_existent_record(
        self, async_client: AsyncClient, db: AsyncSession, mock_search_engine: SearchEngine, owner_auth_header: dict
    ):
        non_existent_record_id = uuid4()

        resp = await async_client.post(
            self.url(),
            headers=owner_auth_header,
            json={
                "items": [
                    {
                        "status": ResponseStatus.draft,
                        "record_id": str(non_existent_record_id),
                    },
                ],
            },
        )

        assert resp.status_code == 200
        assert resp.json() == {
            "items": [
                {
                    "item": None,
                    "error": {
                        "detail": f"Record with id `{non_existent_record_id}` not found",
                    },
                },
            ],
        }

        assert (await db.execute(select(func.count(Response.id)))).scalar() == 0
        assert not mock_search_engine.update_record_response.called

    async def test_response_to_update(
        self,
        async_client: AsyncClient,
        db: AsyncSession,
        mock_search_engine: SearchEngine,
        owner: User,
        owner_auth_header: dict,
    ):
        dataset = await DatasetFactory.create()
        await RatingQuestionFactory.create(name="prompt-quality", required=True, dataset=dataset)

        record = await RecordFactory.create(dataset=dataset)
        response = await ResponseFactory.create(
            status=ResponseStatus.draft,
            values={"prompt-quality": {"value": 1}},
            record=record,
            user=owner,
        )

        resp = await async_client.post(
            self.url(),
            headers=owner_auth_header,
            json={
                "items": [
                    {
                        "values": {"prompt-quality": {"value": 10}},
                        "status": ResponseStatus.submitted,
                        "record_id": str(record.id),
                    },
                ],
            },
        )

        assert resp.status_code == 200

        resp_json = resp.json()
        assert resp_json == {
            "items": [
                {
                    "item": {
                        "id": str(response.id),
                        "values": {"prompt-quality": {"value": 10}},
                        "status": ResponseStatus.submitted.value,
                        "record_id": str(record.id),
                        "user_id": str(owner.id),
                        "inserted_at": datetime.fromisoformat(resp_json["items"][0]["item"]["inserted_at"]).isoformat(),
                        "updated_at": datetime.fromisoformat(resp_json["items"][0]["item"]["updated_at"]).isoformat(),
                    },
                    "error": None,
                },
            ],
        }

        assert (await db.execute(select(func.count(Response.id)))).scalar() == 1

        await db.refresh(response)
        mock_search_engine.update_record_response.assert_called_once_with(response)

    async def test_invalid_response(
        self, async_client: AsyncClient, db: AsyncSession, mock_search_engine: SearchEngine, owner_auth_header: dict
    ):
        dataset = await DatasetFactory.create()
        record = await RecordFactory.create(dataset=dataset)

        resp = await async_client.post(
            self.url(),
            headers=owner_auth_header,
            json={
                "items": [
                    {
                        "values": {"prompt-quality": {"value": 10}},
                        "status": ResponseStatus.submitted,
                        "record_id": str(record.id),
                    },
                ],
            },
        )

        assert resp.status_code == 200
        assert resp.json() == {
            "items": [
                {
                    "item": None,
                    "error": {
                        "detail": "found responses for non configured questions: ['prompt-quality']",
                    },
                },
            ],
        }

        assert (await db.execute(select(func.count(Response.id)))).scalar() == 0
        assert not mock_search_engine.update_record_response.called

    async def test_unauthorized_response(
        self, async_client: AsyncClient, mock_search_engine: SearchEngine, db: AsyncSession
    ):
        dataset = await DatasetFactory.create()
        record = await RecordFactory.create(dataset=dataset)
        annotator = await AnnotatorFactory.create()

        resp = await async_client.post(
            self.url(),
            headers={API_KEY_HEADER_NAME: annotator.api_key},
            json={
                "items": [
                    {
                        "status": ResponseStatus.draft,
                        "record_id": str(record.id),
                    },
                ],
            },
        )

        assert resp.status_code == 200
        assert resp.json() == {
            "items": [
                {
                    "item": None,
                    "error": {
                        "detail": "argilla.api.errors::ForbiddenOperationError(detail=Operation not allowed)",
                    },
                },
            ],
        }

        assert (await db.execute(select(func.count(Response.id)))).scalar() == 0
        assert not mock_search_engine.update_record_response.called

    async def test_no_responses(self, async_client: AsyncClient, owner_auth_header: dict):
        resp = await async_client.post(
            self.url(),
            headers=owner_auth_header,
            json={"items": []},
        )

        assert resp.status_code == 422

    async def test_too_many_responses(self, async_client: AsyncClient, owner_auth_header: dict):
        resp = await async_client.post(
            self.url(),
            headers=owner_auth_header,
            json={"items": [{}] * (self.bulk_max_items() + 1)},
        )

        assert resp.status_code == 422
