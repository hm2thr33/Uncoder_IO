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
from typing import Optional, Union

from app.translator.const import DEFAULT_VALUE_TYPE
from app.translator.core.custom_types.values import ValueType
from app.translator.core.models.platform_details import PlatformDetails
from app.translator.core.render import BaseQueryFieldValue, PlatformQueryRender
from app.translator.core.str_value_manager import StrValue
from app.translator.managers import render_manager
from app.translator.platforms.palo_alto.const import cortex_xql_query_details
from app.translator.platforms.palo_alto.functions import CortexXQLFunctions, cortex_xql_functions
from app.translator.platforms.palo_alto.mapping import (
    CortexXQLLogSourceSignature,
    CortexXQLMappings,
    cortex_xql_mappings,
)
from app.translator.platforms.palo_alto.str_value_manager import cortex_xql_str_value_manager


class CortexXQLFieldValue(BaseQueryFieldValue):
    details: PlatformDetails = cortex_xql_query_details
    str_value_manager = cortex_xql_str_value_manager

    @staticmethod
    def _get_value_type(field_name: str, value: Union[int, str, StrValue], value_type: Optional[str] = None) -> str:  # noqa: ARG004
        if value_type:
            return value_type

        if isinstance(value, StrValue) and value.has_spec_symbols:
            return ValueType.regex_value

        return ValueType.value

    @staticmethod
    def _wrap_str_value(value: str) -> str:
        return f'"{value}"'

    def equal_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            values = ", ".join(
                f"{self._pre_process_value(field, v, value_type=ValueType.value, wrap_str=True)}" for v in value
            )
            return f"{field} in ({values})"

        return f"{field} = {self._pre_process_value(field, value, value_type=ValueType.value, wrap_str=True)}"

    def less_modifier(self, field: str, value: Union[int, str]) -> str:
        return f"{field} < {self._pre_process_value(field, value, value_type=ValueType.value, wrap_str=True)}"

    def less_or_equal_modifier(self, field: str, value: Union[int, str]) -> str:
        return f"{field} <= {self._pre_process_value(field, value, value_type=ValueType.value, wrap_str=True)}"

    def greater_modifier(self, field: str, value: Union[int, str]) -> str:
        return f"{field} > {self._pre_process_value(field, value, value_type=ValueType.value, wrap_str=True)}"

    def greater_or_equal_modifier(self, field: str, value: Union[int, str]) -> str:
        return f"{field} >= {self._pre_process_value(field, value, value_type=ValueType.value, wrap_str=True)}"

    def not_equal_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join([self.not_equal_modifier(field=field, value=v) for v in value])})"
        return f"{field} != {self._pre_process_value(field, value, value_type=ValueType.value, wrap_str=True)}"

    def contains_modifier(self, field: str, value: Union[list, str]) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.contains_modifier(field=field, value=v) for v in value)})"
        if value.endswith("\\"):
            return f'{field} ~= ".*{self._pre_process_value(field, value, value_type=ValueType.regex_value)}.*"'
        return f"{field} contains {self._pre_process_value(field, value, value_type=ValueType.value, wrap_str=True)}"

    def not_contains_modifier(self, field: str, value: Union[list, str]) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.contains_modifier(field=field, value=v) for v in value)})"
        if value.endswith("\\"):
            return f'{field} !~= ".*{self._pre_process_value(field, value, value_type=ValueType.regex_value)}.*"'
        return f"{field} not contains {self._pre_process_value(field, value, ValueType.value, wrap_str=True)}"

    def endswith_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.endswith_modifier(field=field, value=v) for v in value)})"
        return f'{field} ~= ".*{self._pre_process_value(field, value, value_type=ValueType.regex_value)}"'

    def startswith_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            clause = self.or_token.join(self.startswith_modifier(field=field, value=v) for v in value)
            return f"({clause})"
        return f'{field} ~= "{self._pre_process_value(field, value, value_type=ValueType.regex_value)}.*"'

    def regex_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.regex_modifier(field=field, value=v) for v in value)})"
        return f"{field} ~= {self._pre_process_value(field ,value, value_type=ValueType.regex_value, wrap_str=True)}"

    def not_regex_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.regex_modifier(field=field, value=v) for v in value)})"
        return f"{field} !~= {self._pre_process_value(field ,value, value_type=ValueType.regex_value, wrap_str=True)}"

    def is_none(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.is_none(field=field, value=v) for v in value)})"
        return f"{field} = null"

    def is_not_none(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.is_not_none(field=field, value=v) for v in value)})"
        return f"{field} != null"

    def keywords(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.contains_modifier(field=field, value=v) for v in value)})"
        if value.endswith("\\"):
            return f'_raw_log ~= ".*{self._pre_process_value(field ,value, value_type=ValueType.regex_value)}.*"'
        return f"_raw_log contains {self._pre_process_value(field ,value, value_type=ValueType.value, wrap_str=True)}"


@render_manager.register
class CortexXQLQueryRender(PlatformQueryRender):
    details: PlatformDetails = cortex_xql_query_details
    mappings: CortexXQLMappings = cortex_xql_mappings
    is_strict_mapping = True
    raw_log_field_pattern = (
        '| alter {field} = regextract(to_json_string(action_evtlog_data_fields)->{field}{{}}, "\\"(.*)\\"")'
    )
    platform_functions: CortexXQLFunctions = cortex_xql_functions

    or_token = "or"
    and_token = "and"
    not_token = "not"

    field_value_map = CortexXQLFieldValue(or_token=or_token)
    query_pattern = "{prefix} | filter {query} {functions}"
    comment_symbol = "//"
    is_single_line_comment = False

    def __init__(self):
        super().__init__()
        self.platform_functions.manager.post_init_configure(self)

    def generate_prefix(self, log_source_signature: CortexXQLLogSourceSignature, functions_prefix: str = "") -> str:
        functions_prefix = f"{functions_prefix} | " if functions_prefix else ""
        return f"{functions_prefix}{log_source_signature}"
