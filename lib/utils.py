from typing import Any, List

def index_dataclass(dataclass_list: List[Any], field_name: str, value: Any) -> int:
    """
    Find the index of the first dataclass instance in the list that matches the given field value.
    
    :param dataclass_list: List of dataclass instances.
    :param field_name: The name of the field to search for.
    :param value: The value to search for.
    :return: Index of the first matching dataclass instance.
    :raises ValueError: If no dataclass instance with the specified field value is found.
    """
    for index, item in enumerate(dataclass_list):
        if getattr(item, field_name) == value:
            return index
    raise ValueError(f"{value} not found in {field_name}")