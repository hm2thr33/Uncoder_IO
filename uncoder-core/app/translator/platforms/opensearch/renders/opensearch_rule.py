"""
Uncoder IO Community Edition License
-----------------------------------------------------------------
Copyright (c) 2024 SOC Prime, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-----------------------------------------------------------------
"""

import copy
from typing import Optional

import ujson

from app.translator.core.custom_types.meta_info import SeverityType
from app.translator.core.mapping import SourceMapping
from app.translator.core.models.platform_details import PlatformDetails
from app.translator.core.models.query_container import MetaInfoContainer
from app.translator.platforms.opensearch.const import OPENSEARCH_RULE, opensearch_rule_details
from app.translator.platforms.opensearch.mapping import OpenSearchMappings, opensearch_mappings
from app.translator.platforms.opensearch.renders.opensearch import OpenSearchFieldValue, OpenSearchQueryRender

_SEVERITIES_MAP = {SeverityType.critical: "5", SeverityType.high: "4", SeverityType.medium: "3", SeverityType.low: "2"}


class OpenSearchRuleFieldValue(OpenSearchFieldValue):
    details: PlatformDetails = opensearch_rule_details


class OpenSearchRuleRender(OpenSearchQueryRender):
    details: PlatformDetails = opensearch_rule_details
    mappings: OpenSearchMappings = opensearch_mappings

    or_token = "OR"
    and_token = "AND"
    not_token = "NOT"

    field_value_map = OpenSearchRuleFieldValue(or_token=or_token)
    query_pattern = "{prefix} {query} {functions}"

    def finalize_query(
        self,
        prefix: str,
        query: str,
        functions: str,
        meta_info: Optional[MetaInfoContainer] = None,
        source_mapping: Optional[SourceMapping] = None,  # noqa: ARG002
        not_supported_functions: Optional[list] = None,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> str:
        query = super().finalize_query(prefix=prefix, query=query, functions=functions)
        rule = copy.deepcopy(OPENSEARCH_RULE)
        rule["name"] = meta_info.title
        rule["inputs"][0]["search"]["query"]["query"]["bool"]["must"][0]["query_string"]["query"] = query
        rule["triggers"][0]["name"] = meta_info.title
        rule["triggers"][0]["severity"] = _SEVERITIES_MAP[meta_info.severity]
        rule_str = ujson.dumps(rule, indent=4, sort_keys=False)
        if not_supported_functions:
            rendered_not_supported = self.render_not_supported_functions(not_supported_functions)
            return rule_str + rendered_not_supported
        return rule_str
