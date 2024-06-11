from typing import ClassVar

from app.translator.core.custom_types.values import ValueType
from app.translator.core.escape_manager import EscapeManager
from app.translator.core.models.escape_details import EscapeDetails


class CortexXQLEscapeManager(EscapeManager):
    escape_map: ClassVar[dict[str, list[EscapeDetails]]] = {
        ValueType.regex_value: [
            EscapeDetails(pattern=r'([_!@#$%^&*=+()\[\]{}|;:\'",.<>?/`~\-\s\\])', escape_symbols=r"\\\1")
        ],
        ValueType.value: [EscapeDetails(pattern=r"([\*\"\\])", escape_symbols=r"\\\1")],
    }


cortex_xql_escape_manager = CortexXQLEscapeManager()
