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

import re
from typing import Union

from app.translator.core.models.query_container import RawQueryContainer, TokenizedQueryContainer
from app.translator.core.parser import PlatformQueryParser
from app.translator.platforms.base.aql.const import NUM_VALUE_PATTERN, SINGLE_QUOTES_VALUE_PATTERN
from app.translator.platforms.base.aql.log_source_map import LOG_SOURCE_FUNCTIONS_MAP
from app.translator.platforms.base.aql.mapping import AQLMappings, aql_mappings
from app.translator.platforms.base.aql.tokenizer import AQLTokenizer
from app.translator.tools.utils import get_match_group


class AQLQueryParser(PlatformQueryParser):
    tokenizer = AQLTokenizer()
    mappings: AQLMappings = aql_mappings

    log_source_functions = ("LOGSOURCENAME", "LOGSOURCEGROUPNAME")
    log_source_function_pattern = r"\(?(?P<key>___func_name___\([a-zA-Z]+\))(?:\s+like\s+|\s+ilike\s+|\s*=\s*)'(?P<value>[%a-zA-Z\s]+)'\s*\)?\s+(?:and|or)?\s"  # noqa: E501

    log_source_key_types = ("devicetype", "category", "qid", "qideventcategory", *LOG_SOURCE_FUNCTIONS_MAP.keys())
    log_source_pattern = rf"___source_type___(?:\s+like\s+|\s+ilike\s+|\s*=\s*)(?:{SINGLE_QUOTES_VALUE_PATTERN}|{NUM_VALUE_PATTERN})(?:\s+(?:and|or)\s+|\s+)?"  # noqa: E501
    num_value_pattern = r"[0-9]+"
    multi_num_log_source_pattern = (
        rf"___source_type___\s+in\s+\((?P<value>(?:{num_value_pattern}(?:\s*,\s*)?)+)\)(?:\s+(?:and|or)\s+|\s+)?"
    )
    str_value_pattern = r"""(?:')(?P<s_q_value>(?:[:a-zA-Z\*0-9=+%#\-\/\\,_".$&^@!\(\)\{\}\s]|'')+)(?:')"""
    multi_str_log_source_pattern = (
        rf"""___source_type___\s+in\s+\((?P<value>(?:{str_value_pattern}(?:\s*,\s*)?)+)\)(?:\s+(?:and|or)\s+|\s+)?"""
    )

    table_pattern = r"\sFROM\s(?P<table>[a-zA-Z\.\-\*]+)\sWHERE\s"

    def __clean_query(self, query: str) -> str:
        for func_name in self.log_source_functions:
            pattern = self.log_source_function_pattern.replace("___func_name___", func_name)
            while search := re.search(pattern, query, flags=re.IGNORECASE):
                pos_start = search.start()
                pos_end = search.end()
                query = query[:pos_start] + query[pos_end:]

        return query

    @staticmethod
    def __parse_multi_value_log_source(
        match: re.Match, query: str, pattern: str
    ) -> tuple[str, Union[list[str], list[int]]]:
        value = match.group("value")
        pos_start = match.start()
        pos_end = match.end()
        query = query[:pos_start] + query[pos_end:]
        return query, re.findall(pattern, value)

    def __map_log_source_value(self, logsource_key: str, value: Union[str, int]) -> tuple[str, Union[int, str]]:
        if log_source_map := LOG_SOURCE_FUNCTIONS_MAP.get(logsource_key):
            return log_source_map.name, log_source_map.id_map.get(value, value)
        return logsource_key, value

    def __parse_log_sources(self, query: str) -> tuple[dict[str, Union[list[str], list[int]]], str]:
        log_sources = {}

        if search := re.search(self.table_pattern, query, flags=re.IGNORECASE):
            pos_end = search.end()
            query = query[pos_end:]

        for log_source_key in self.log_source_key_types:
            pattern = self.log_source_pattern.replace("___source_type___", log_source_key)
            while search := re.search(pattern, query, flags=re.IGNORECASE):
                num_value = get_match_group(search, group_name="num_value")
                str_value = get_match_group(search, group_name="s_q_value")
                value = num_value and int(num_value) or str_value
                log_source_key, value = self.__map_log_source_value(log_source_key, value)
                log_sources.setdefault(log_source_key, []).append(value)
                pos_start = search.start()
                pos_end = search.end()
                query = query[:pos_start] + query[pos_end:]

            pattern = self.multi_num_log_source_pattern.replace("___source_type___", log_source_key)
            if search := re.search(pattern, query, flags=re.IGNORECASE):
                query, values = self.__parse_multi_value_log_source(search, query, self.num_value_pattern)
                values = [int(v) for v in values]
                log_sources.setdefault(log_source_key, []).extend(values)

            pattern = self.multi_str_log_source_pattern.replace("___source_type___", log_source_key)
            if search := re.search(pattern, query, flags=re.IGNORECASE):
                query, values = self.__parse_multi_value_log_source(search, query, self.str_value_pattern)
                log_sources.setdefault(log_source_key, []).extend(values)

        return log_sources, query

    def _parse_query(self, text: str) -> tuple[str, dict[str, Union[list[str], list[int]]]]:
        query = self.__clean_query(text)
        log_sources, query = self.__parse_log_sources(query)
        return query, log_sources

    def parse(self, raw_query_container: RawQueryContainer) -> TokenizedQueryContainer:
        query, log_sources = self._parse_query(raw_query_container.query)
        tokens, source_mappings = self.get_tokens_and_source_mappings(query, log_sources)
        fields_tokens = self.get_fields_tokens(tokens=tokens)
        meta_info = raw_query_container.meta_info
        meta_info.query_fields = fields_tokens
        meta_info.source_mapping_ids = [source_mapping.source_id for source_mapping in source_mappings]
        return TokenizedQueryContainer(tokens=tokens, meta_info=meta_info)
