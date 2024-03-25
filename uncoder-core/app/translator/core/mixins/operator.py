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

from typing import Optional, Union

from app.translator.core.custom_types.tokens import OperatorType
from app.translator.core.models.identifier import Identifier


class WildCardMixin:
    @staticmethod
    def _clean_value(value: str, wildcard_symbol: str) -> str:
        return value.strip(wildcard_symbol)

    def get_field_value_operator(
        self, value: Union[str, list[str]], operator: Optional[str] = None, wildcard_symbol: Optional[str] = None
    ) -> tuple[Union[list[str], str], Identifier]:
        if wildcard_symbol:
            value = self._clean_value(value, wildcard_symbol)
        return value, Identifier(token_type=operator)


class OperatorBasedMixin(WildCardMixin):
    def get_field_value_operator(
        self, value: Union[str, list[str]], operator: Optional[str] = None, wildcard_symbol: Optional[str] = None
    ) -> tuple[Union[list[str], str], Identifier]:
        value, operator = self.__get_value_operator(operator=operator, value=value)
        if wildcard_symbol:
            value = self._clean_value(value, wildcard_symbol)
        return value, operator

    @staticmethod
    def __get_value_operator(operator: str, value: Union[str, list[str]]) -> tuple[Union[list[str], str], Identifier]:
        if operator == OperatorType.CONTAINS:
            operator = Identifier(token_type=OperatorType.CONTAINS)
        elif operator == OperatorType.ENDSWITH:
            operator = Identifier(token_type=OperatorType.ENDSWITH)
        elif operator == OperatorType.STARTSWITH:
            operator = Identifier(token_type=OperatorType.STARTSWITH)
        elif operator == OperatorType.REGEX:
            operator = Identifier(token_type=OperatorType.REGEX)
        elif operator == OperatorType.EQ:
            operator = Identifier(token_type=OperatorType.EQ)
        else:
            raise Exception("Unknown operator")
        return value, operator
