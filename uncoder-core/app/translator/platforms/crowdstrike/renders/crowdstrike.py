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

from app.translator.core.models.platform_details import PlatformDetails
from app.translator.platforms.base.spl.renders.spl import SplFieldValue, SplQueryRender
from app.translator.platforms.crowdstrike.const import crowdstrike_query_details
from app.translator.platforms.crowdstrike.functions import CrowdStrikeFunctions, crowd_strike_functions
from app.translator.platforms.crowdstrike.mapping import CrowdstrikeMappings, crowdstrike_mappings


class CrowdStrikeFieldValue(SplFieldValue):
    details = crowdstrike_query_details


class CrowdStrikeQueryRender(SplQueryRender):
    details: PlatformDetails = crowdstrike_query_details
    query_pattern = "{prefix} {query} {functions}"
    mappings: CrowdstrikeMappings = crowdstrike_mappings
    platform_functions: CrowdStrikeFunctions = crowd_strike_functions

    or_token = "OR"
    field_value_map = CrowdStrikeFieldValue(or_token=or_token)
    comment_symbol = "`"

    def __init__(self):
        super().__init__()
        self.platform_functions.manager.init_search_func_render(self)
