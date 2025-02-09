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
import logging
from typing import Tuple

from opensearchpy import OpenSearch
from packaging.version import parse

from argilla.server.daos.backend.base import GenericSearchError
from argilla.server.daos.backend.client_adapters import ElasticsearchClient, IClientAdapter, OpenSearchClient
from argilla.server.settings import settings as server_settings

_LOGGER = logging.getLogger("argilla")


class ClientAdapterFactory:
    @classmethod
    def get(
        cls,
        hosts: str,
        index_shards: int,
        ssl_verify: bool,
        ca_path: str,
        retry_on_timeout: bool = True,
        max_retries: int = 5,
    ) -> IClientAdapter:
        client_config = dict(
            hosts=hosts,
            verify_certs=ssl_verify,
            ca_certs=ca_path,
            retry_on_timeout=retry_on_timeout,
            max_retries=max_retries,
        )

        version, distribution = cls._fetch_cluster_version_info(client_config)

        if distribution != server_settings.search_engine:
            _LOGGER.warning(
                f"The search engine distribution is not the same as the one configured in the server. "
                f"The configuration will be automatically updated with ARGILLA_SEARCH_ENGINE={distribution}."
            )
            server_settings.search_engine = distribution

        if distribution == "elasticsearch" and parse("8.5.0") <= parse(version):
            client_class = ElasticsearchClient
        elif distribution == "opensearch" and parse("2.4.0") <= parse(version):
            client_class = OpenSearchClient
        else:
            raise ValueError(
                f"Unsupported ElasticSearch/OpenSearch backend version :{version}. "
                f"Minimal supported version are `8.5.0` for Elasticsearch and `2.4.0` for OpenSearch. "
                "Please, upgrade the backend to a supported version."
            )

        return client_class(index_shards=index_shards, config_backend=client_config)

    @classmethod
    def _fetch_cluster_version_info(cls, client_config: dict) -> Tuple[str, str]:
        try:
            # All security config will be used here.
            # See here https://opensearch.org/docs/latest/clients/index/#legacy-clients
            client = OpenSearch(**client_config)
            data = client.info()

            version_info = data["version"]
            version: str = version_info["number"]
            distribution: str = version_info.get("distribution", "elasticsearch")

            return version, distribution
        except Exception as error:
            raise GenericSearchError(error)
