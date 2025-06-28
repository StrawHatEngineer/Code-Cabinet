import logging
from typing import Any, Dict, List, Text, Tuple
from instabase.provenance.registration import register_fn

ValidationTuple = Tuple[bool, Text]


@register_fn(provenance=False)
def always_fail(*args: Any, **kwargs: Any) -> ValidationTuple:
  return False, 'Always fail'


@register_fn(provenance=False)
def always_pass(*args: Any, **kwargs: Any) -> ValidationTuple:
  return True, None


@register_fn(provenance=False)
def validate_total(total: Text, **kwargs: Any) -> ValidationTuple:
  if (str(total) == '17.01'):
    logging.info('Total is 17.01 - custom fail!!')
    return False, 'Total is 17.01 - custom fail!!'
  return True, None


@register_fn(provenance=False)
def validate_dict_keypath(dict_field: Dict,
                          **kwargs: Any) -> Dict[Text, ValidationTuple]:
  return {
      'dict_field.key1.nestedkey':
      (False, 'Field dict_field had a failure at keypath key1.nestedkey')
  }


@register_fn(provenance=False)
def validate_list_index(list_field: List,
                        **kwargs: Any) -> Dict[Text, ValidationTuple]:
  return {'list_field.3': (False, 'Field list_field had a failure at index 3')}


@register_fn(provenance=False)
def validate_table_cell(table_field: List,
                        **kwargs: Any) -> Dict[Text, ValidationTuple]:
  return {
      'table_field.0.3_3.9_9':
      (False,
       'Field table_field had a failure for table index 0, row range [3,3], col range [9,9]'
       )
  }
