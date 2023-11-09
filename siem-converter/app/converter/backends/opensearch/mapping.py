from typing import List, Optional

from app.converter.core.mapping import BasePlatformMappings, LogSourceSignature, SourceMapping, DEFAULT_MAPPING_NAME


class OpenSearchLogSourceSignature(LogSourceSignature):
    def __init__(self, indices: Optional[List[str]], default_source: dict):
        self.indices = set(indices or [])
        self._default_source = default_source or {}

    def is_suitable(self, index: List[str]) -> bool:
        return set(index).issubset(self.indices)

    def __str__(self) -> str:
        return self._default_source.get("index", "")


class OpenSearchMappings(BasePlatformMappings):
    def prepare_log_source_signature(self, mapping: dict) -> OpenSearchLogSourceSignature:
        indices = mapping.get("log_source", {}).get("index")
        default_log_source = mapping["default_log_source"]
        return OpenSearchLogSourceSignature(indices=indices, default_source=default_log_source)

    def get_suitable_source_mappings(self, field_names: List[str], index: Optional[str]) -> List[SourceMapping]:
        suitable_source_mappings = []
        for source_mapping in self._source_mappings.values():
            if source_mapping.source_id == DEFAULT_MAPPING_NAME:
                continue

            log_source_signature: OpenSearchLogSourceSignature = source_mapping.log_source_signature
            if index and log_source_signature.is_suitable(index=index):
                if source_mapping.fields_mapping.is_suitable(field_names):
                    suitable_source_mappings.append(source_mapping)
            else:
                if source_mapping.fields_mapping.is_suitable(field_names):
                    suitable_source_mappings.append(source_mapping)

        if not suitable_source_mappings:
            suitable_source_mappings = [self._source_mappings[DEFAULT_MAPPING_NAME]]

        return suitable_source_mappings


opensearch_mappings = OpenSearchMappings(platform_dir="opensearch")