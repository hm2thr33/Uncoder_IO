"""
Uncoder IO Commercial Edition License
-----------------------------------------------------------------
Copyright (c) 2024 SOC Prime, Inc.

This file is part of the Uncoder IO Commercial Edition ("CE") and is
licensed under the Uncoder IO Non-Commercial License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://github.com/UncoderIO/UncoderIO/blob/main/LICENSE

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-----------------------------------------------------------------
"""

from typing import Any, Union

import yaml

from app.translator.const import DEFAULT_VALUE_TYPE
from app.translator.core.custom_types.meta_info import SeverityType
from app.translator.core.custom_types.tokens import OperatorType
from app.translator.core.mapping import DEFAULT_MAPPING_NAME, SourceMapping
from app.translator.core.models.field import FieldValue, Keyword
from app.translator.core.models.query_container import RawQueryContainer, TokenizedQueryContainer
from app.translator.core.models.platform_details import PlatformDetails
from app.translator.core.render import QueryRender
from app.translator.core.str_value_manager import StrValue
from app.translator.platforms.sigma.const import SIGMA_RULE_DETAILS
from app.translator.platforms.sigma.mapping import SigmaLogSourceSignature, SigmaMappings, sigma_mappings
from app.translator.platforms.sigma.models.compiler import DataStructureCompiler
from app.translator.platforms.sigma.models.group import Group
from app.translator.platforms.sigma.models.operator import AND, NOT, OR
from app.translator.platforms.sigma.str_value_manager import sigma_str_value_manager


class SigmaRender(QueryRender):
    selection_name = "selection"
    selection_num = 0
    keyword_name = "keyword"
    keyword_num = 0

    mappings: SigmaMappings = sigma_mappings
    details: PlatformDetails = PlatformDetails(**SIGMA_RULE_DETAILS)
    str_value_manager = sigma_str_value_manager

    @property
    def selection(self):
        return f"{self.selection_name}{self.selection_num}"

    @property
    def keyword(self):
        return f"{self.selection_name}{self.keyword_num}"

    def increase_selection(self) -> None:
        self.selection_num += 1

    def increase_keyword(self) -> None:
        self.keyword_num += 1

    def reset_counters(self) -> None:
        self.keyword_num = 0
        self.selection_num = 0

    def generate_data_structure(self, data: Any, source_mapping: SourceMapping):
        if isinstance(data, OR):
            return self.generate_or(data, source_mapping)
        elif isinstance(data, AND):
            return self.generate_and(data, source_mapping)
        elif isinstance(data, NOT):
            return self.generate_not(data, source_mapping)
        elif isinstance(data, FieldValue):
            return self.generate_field(data, source_mapping)
        elif isinstance(data, Keyword):
            return self.generate_keyword(data)
        elif isinstance(data, Group):
            return self.generate_group(data, source_mapping)
        return None

    def generate_group(self, data: Any, source_mapping: SourceMapping):
        sub_group = self.generate_data_structure(data.items, source_mapping)
        if isinstance(sub_group, list):
            return sub_group
        if condition := sub_group.get("condition"):
            sub_group["condition"] = (
                condition
                if condition.count(self.selection_name) == 1 or condition.count(self.keyword_name) == 1
                else f"({condition})"
            )
        return sub_group

    def generate_or(self, data: Any, source_mapping: SourceMapping):
        result = {}
        condition = ""
        for i, item in enumerate(data.items):
            updated_node = self.generate_data_structure(item, source_mapping)
            if isinstance(updated_node, list):
                if result and isinstance(result.get(self.keyword), list):
                    result[self.keyword].extend(updated_node)
                else:
                    if self.keyword_num == self.selection_num:
                        self.increase_keyword()
                    self.increase_selection()
                    condition += f"{' or ' if condition else ''}{self.selection}"
                    result[self.selection] = updated_node
            elif (
                result
                and len(set(result.get(self.selection, [])).intersection(set(updated_node))) != 0
                and isinstance(data.items[i - 1], FieldValue)
                and len(updated_node) == 1
                and self.selection not in updated_node
            ):
                field_name = list(updated_node.keys())[0]
                if isinstance(result[self.selection][field_name], list):
                    result[self.selection][field_name].append(updated_node[field_name])
                else:
                    result[self.selection][field_name] = [result[self.selection][field_name], updated_node[field_name]]
            elif not result and self.selection in updated_node:
                result = updated_node
                t_c = result.get("condition")
                condition = (
                    t_c
                    if not condition
                    else f"{condition} or {t_c if t_c.count(self.selection_name) == 1 else f'({t_c})'}"
                )
            elif result and self.selection in updated_node:
                result.update(updated_node)
                t_c = result.get("condition")
                condition += (
                    f"{' or ' if condition else ''}{t_c if t_c.count(self.selection_name) == 1 else f'({t_c})'}"
                )
            else:
                self.increase_selection()
                result[self.selection] = updated_node
                condition += f"{' or ' if condition else ''}{self.selection}"
        result.update({"condition": condition})
        self.increase_keyword()
        return result

    def generate_and(self, data: Any, source_mapping: SourceMapping):
        result = {}
        condition = ""
        for item in data.items:
            updated_node = self.generate_data_structure(item, source_mapping)
            if isinstance(updated_node, list):
                self.increase_keyword()
                self.increase_selection()
                condition += f"{' and ' if condition else ''}{self.selection}"
                result[self.selection] = updated_node
            elif (
                result
                and isinstance(updated_node, dict)
                and isinstance(result.get(self.selection, []), dict)
                and len(set(result.get(self.selection, [])).intersection(set(updated_node))) == 0
                and self.selection not in updated_node
            ):
                if isinstance(result[self.selection], list):
                    result[self.selection].append(updated_node)
                else:
                    result[self.selection].update(updated_node)
            elif not result and self.selection in updated_node:
                result = updated_node
                t_c = result.get("condition")
                condition = t_c if not condition else f"{condition} and {t_c}"
            elif result and self.selection in updated_node:
                result.update(updated_node)
                condition += f"{' and ' if condition else ''}{result.get('condition')}"
            else:
                self.increase_selection()
                result[self.selection] = updated_node
                condition += f"{' and ' if condition else ''}{self.selection}"
        result.update({"condition": condition})
        self.increase_keyword()
        return result

    def generate_not(self, data: Any, source_mapping: SourceMapping):
        not_node = self.generate_data_structure(data.items, source_mapping)
        if isinstance(not_node, list):
            self.increase_selection()
            not_node = {self.selection: not_node, "condition": f"not {self.selection}"}
        elif not not_node.get("condition"):
            self.increase_selection()
            if list(not_node.keys())[0] == self.keyword_name:
                not_node = list(not_node.values())
            not_node = {self.selection: not_node, "condition": f"not {self.selection}"}
        elif condition := not_node.get("condition"):
            not_node["condition"] = f"not {condition}"
        return not_node

    @staticmethod
    def map_field(source_mapping: SourceMapping, generic_field_name: str) -> str:
        field_name = source_mapping.fields_mapping.get_platform_field_name(generic_field_name)
        return field_name or generic_field_name

    def generate_field(self, data: FieldValue, source_mapping: SourceMapping):
        source_id = source_mapping.source_id
        generic_field_name = data.field.get_generic_field_name(source_id) or data.field.source_name
        field_name = self.map_field(source_mapping, generic_field_name)
        if data.operator.token_type not in (
            OperatorType.EQ,
            OperatorType.LT,
            OperatorType.LTE,
            OperatorType.GT,
            OperatorType.GTE,
            OperatorType.NEQ,
        ):
            field_name = f"{field_name}|{data.operator.token_type}"

        values = self.__pre_process_values(data.values)
        if len(values) == 1:
            return {field_name: values[0]}
        elif len(values) == 0:
            return {field_name: ""}
        return {field_name: values}

    def __pre_process_values(self, values: DEFAULT_VALUE_TYPE) -> list[Union[int, str]]:
        processed = []
        for v in values:
            if isinstance(v, StrValue):
                processed.append(self.str_value_manager.from_container_to_str(v))
            elif isinstance(v, str):
                processed.append(v)
            else:
                processed.append(v)

        return processed

    def generate_keyword(self, data: Keyword):
        return self.__pre_process_values(data.values)

    def __base_detection(self, data: dict):
        self.increase_selection()
        return {self.selection: data, "condition": self.selection}

    @staticmethod
    def generate_aggregation(detection: dict, agg_data):
        if timeframe := agg_data.get("timeframe"):
            detection.update({"timeframe": timeframe})
        if agg_func := agg_data.get("agg_func"):
            agg_condition = f" | {agg_func}"
            if agg_field := agg_data.get("agg_field"):
                agg_condition += f"({agg_field})"
            else:
                agg_condition += "()"

            if group_by := agg_data.get("group_by"):
                agg_condition += f" by {', '.join(group_by)}"

            if agg_value := agg_data.get("agg_value"):
                agg_condition += f" {agg_value}"

            detection["condition"] += agg_condition
        return detection

    def generate_detection(self, data: Any, source_mapping: SourceMapping) -> dict:
        detection = self.generate_data_structure(data, source_mapping)
        if self.selection not in detection:
            detection = self.__base_detection(detection)
        condition = detection.pop("condition")
        if condition.startswith("(") and condition.endswith(")") and "(" not in condition[1:-1]:
            condition = condition.rstrip(")").lstrip("(")
        detection.update({"condition": condition})
        self.reset_counters()

        return detection

    def __get_source_mapping(self, source_mapping_ids: list[str]) -> SourceMapping:
        for source_mapping_id in source_mapping_ids:
            if source_mapping := self.mappings.get_source_mapping(source_mapping_id):
                return source_mapping

        return self.mappings.get_source_mapping(DEFAULT_MAPPING_NAME)

    def _generate_from_raw_query_container(self, query_container: RawQueryContainer) -> str:
        raise NotImplementedError

    def _generate_from_tokenized_query_container(self, query_container: TokenizedQueryContainer) -> str:
        self.reset_counters()

        meta_info = query_container.meta_info
        source_mapping = self.__get_source_mapping(meta_info.source_mapping_ids)
        log_source_signature: SigmaLogSourceSignature = source_mapping.log_source_signature
        prepared_data_structure = DataStructureCompiler().generate(tokens=query_container.tokens)

        rule = {
            "title": meta_info.title or "Autogenerated Sigma Rule",
            "id": meta_info.id,
            "description": meta_info.description,
            "status": "experimental",
            "author": meta_info.author,
            "references": meta_info.references,
            "tags": meta_info.tags,
            "logsource": log_source_signature.log_sources,
            "fields": [],
            "detection": self.generate_detection(prepared_data_structure, source_mapping=source_mapping),
            "level": meta_info.severity or SeverityType.low,
            "falsepositives": "",
        }
        return yaml.dump(rule, default_flow_style=False, sort_keys=False)

    def generate(self, query_container: Union[RawQueryContainer, TokenizedQueryContainer]) -> str:
        if isinstance(query_container, RawQueryContainer):
            return self._generate_from_raw_query_container(query_container)

        return self._generate_from_tokenized_query_container(query_container)
