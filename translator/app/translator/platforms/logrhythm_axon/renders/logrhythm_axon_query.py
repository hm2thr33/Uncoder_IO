"""
Uncoder IO Community Edition License
-----------------------------------------------------------------
Copyright (c) 2023 SOC Prime, Inc.

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
from typing import Union

from app.translator.const import DEFAULT_VALUE_TYPE
from app.translator.core.custom_types.tokens import LogicalOperatorType
from app.translator.core.exceptions.core import StrictPlatformException
from app.translator.core.exceptions.render import BaseRenderException
from app.translator.core.mapping import LogSourceSignature, SourceMapping
from app.translator.core.models.field import FieldValue, Keyword
from app.translator.core.models.functions.base import ParsedFunctions
from app.translator.core.models.identifier import Identifier
from app.translator.core.models.parser_output import MetaInfoContainer
from app.translator.core.models.platform_details import PlatformDetails
from app.translator.core.render import BaseQueryFieldValue, BaseQueryRender
from app.translator.platforms.logrhythm_axon.const import logrhythm_axon_query_details
from app.translator.platforms.logrhythm_axon.mapping import LogRhythmAxonMappings, logrhythm_axon_mappings
from app.translator.platforms.microsoft.escape_manager import microsoft_escape_manager


class LogRhythmRegexRenderException(BaseRenderException):
    ...


class LogRhythmAxonFieldValue(BaseQueryFieldValue):
    details: PlatformDetails = logrhythm_axon_query_details
    escape_manager = microsoft_escape_manager

    def __is_complex_regex(self, regex: str) -> bool:
        regex_items = ("[", "]", "(", ")", "{", "}", "+", "?", "^", "$", "\d", "\w", "\s", "-")
        return any(v in regex_items for v in regex)

    def __is_regex(self, value: str) -> bool:
        regex_items = ("", "[", "]", "(", ")", "{", "}", "*", "+", "?", "^", "$", "|", ".", "\d", "\w", "\s", "\\", "-")
        return any(v in regex_items for v in value)

    def __regex_to_str_list(self, value: Union[int, str]) -> list[list[str]]:
        value_groups = []
        start = 0

        for i in range(1, len(value)):
            if value[i] == "|" and value[i - 1] != "\\":
                if start < i:
                    value_groups.append(value[start:i])
                start = i + 1
        if start < len(value):
            value_groups.append(value[start:])

        joined_components = []
        for value_group in value_groups:
            inner_joined_components = []
            not_joined_components = []

            for i in range(len(value_group)):
                if value_group[i] == "*" and i > 0 and value_group[i - 1] != "\\":
                    inner_joined_components.append("".join(not_joined_components))
                    not_joined_components = []
                else:
                    not_joined_components.append(value_group[i])
            inner_joined_components.append("".join(not_joined_components))
            joined_components.append(inner_joined_components)

        return joined_components

    @staticmethod
    def __escape_value(value: Union[int, str]) -> Union[int, str]:
        return value.replace("'", "''") if isinstance(value, str) else value

    def equal_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, str):
            return f'{field} = "{self.__escape_value(value)}"'
        if isinstance(value, list):
            prepared_values = ", ".join(f"{self.__escape_value(v)}" for v in value)
            operator = "IN" if all(isinstance(v, str) for v in value) else "in"
            return f"{field} {operator} [{prepared_values}]"
        return f'{field} = "{self.apply_value(value)}"'

    def less_modifier(self, field: str, value: Union[int, str]) -> str:
        if isinstance(value, int):
            return f"{field} < {value}"
        return f"{field} < '{self.apply_value(value)}'"

    def less_or_equal_modifier(self, field: str, value: Union[int, str]) -> str:
        if isinstance(value, int):
            return f"{field} <= {value}"
        return f"{field} <= {self.apply_value(value)}"

    def greater_modifier(self, field: str, value: Union[int, str]) -> str:
        if isinstance(value, int):
            return f"{field} > {value}"
        return f"{field} > {self.apply_value(value)}"

    def greater_or_equal_modifier(self, field: str, value: Union[int, str]) -> str:
        if isinstance(value, int):
            return f"{field} >= {value}"
        return f"{field} >= {self.apply_value(value)}"

    def not_equal_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join([self.not_equal_modifier(field=field, value=v) for v in value])})"
        if isinstance(value, int):
            return f"{field} != {value}"
        return f"{field} != {self.apply_value(value)}"

    def contains_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.contains_modifier(field=field, value=v) for v in value)})"
        if isinstance(value, str) and self.__is_regex(value):
            if self.__is_complex_regex(value):
                raise LogRhythmRegexRenderException
            values = self.__regex_to_str_list(value)
            return (
                "("
                + self.or_token.join(
                    " AND ".join(f'{field} CONTAINS "{self.__escape_value(value)}"' for value in value_list)
                    for value_list in values
                )
                + ")"
            )
        return f'{field} CONTAINS "{self.__escape_value(value)}"'

    def endswith_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.endswith_modifier(field=field, value=v) for v in value)})"
        value = f".*{self.__escape_value(value)}" if not value.startswith(".*") else self.__escape_value(value)
        return f'{field} matches "{value}$"'

    def startswith_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.startswith_modifier(field=field, value=v) for v in value)})"
        value = f"{self.__escape_value(value)}.*" if not value.endswith(".*") else self.__escape_value(value)
        return f'{field} matches "^{self.__escape_value(value)}"'

    def __regex_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        return f'{field} matches "{value}"'

    def regex_modifier(self, field: str, value: DEFAULT_VALUE_TYPE) -> str:
        if isinstance(value, list):
            return f"({self.or_token.join(self.__regex_modifier(field=field, value=v) for v in value)})"
        return self.__regex_modifier(field, value)


class LogRhythmAxonQueryRender(BaseQueryRender):
    details: PlatformDetails = logrhythm_axon_query_details

    or_token = "OR"
    and_token = "AND"
    not_token = "NOT"

    field_value_map = LogRhythmAxonFieldValue(or_token=or_token)
    query_pattern = "{prefix} AND {query}"

    mappings: LogRhythmAxonMappings = logrhythm_axon_mappings
    comment_symbol = "//"
    is_multi_line_comment = True
    is_strict_mapping = True

    def generate_prefix(self, log_source_signature: LogSourceSignature) -> str:
        return str(log_source_signature)

    def apply_token(self, token: Union[FieldValue, Keyword, Identifier], source_mapping: SourceMapping) -> str:
        if isinstance(token, FieldValue):
            try:
                mapped_fields = self.map_field(token.field, source_mapping)
            except StrictPlatformException:
                try:
                    return self.field_value_map.apply_field_value(
                        field="general_information.raw_message",
                        operator=Identifier(token_type="contains"),
                        value=token.value,
                    )
                except LogRhythmRegexRenderException as exc:
                    raise LogRhythmRegexRenderException(
                        f"Uncoder does not support complex regexp for unmapped field:"
                        f" {token.field.source_name} for LogRhythm Axon"
                    ) from exc
            if len(mapped_fields) > 1:
                return self.group_token % self.operator_map[LogicalOperatorType.OR].join(
                    [
                        self.field_value_map.apply_field_value(field=field, operator=token.operator, value=token.value)
                        for field in mapped_fields
                    ]
                )
            return self.field_value_map.apply_field_value(
                field=mapped_fields[0], operator=token.operator, value=token.value
            )

        if isinstance(token, Keyword):
            return self.field_value_map.apply_field_value(field=None, operator=token.operator, value=token.value)
        if token.token_type in LogicalOperatorType:
            return self.operator_map.get(token.token_type)

        return token.token_type

    def generate(self, query: list, meta_info: MetaInfoContainer, functions: ParsedFunctions) -> str:
        queries_map = {}
        source_mappings = self._get_source_mappings(meta_info.source_mapping_ids)

        for source_mapping in source_mappings:
            prefix = self.generate_prefix(source_mapping.log_source_signature)
            if "product" in meta_info.parsed_logsources:
                prefix = f"{prefix} CONTAINS {meta_info.parsed_logsources['product'][0]}"
            else:
                prefix = f"{prefix} CONTAINS anything"

            result = self.generate_query(query=query, source_mapping=source_mapping)

            finalized_query = self.finalize_query(
                prefix=prefix,
                query=result,
                functions=self.generate_functions(functions.functions, source_mapping),
                not_supported_functions=functions.not_supported,
                meta_info=meta_info,
                source_mapping=source_mapping,
            )
            queries_map[source_mapping.source_id] = finalized_query

        return self.finalize(queries_map)