# Lint as: python3
# Copyright 2021 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""BaseModelParams class definition."""

import abc
from typing import List, Type, TypeVar

from lingvo.jax import base_input
from lingvo.jax import py_utils

InstantiableParams = py_utils.InstantiableParams
_BaseModelParamsT = TypeVar('_BaseModelParamsT', bound='BaseModelParams')
BaseModelParamsT = Type[_BaseModelParamsT]


class BaseModelParams(metaclass=abc.ABCMeta):
  """Encapsulates the parameters for a model."""

  @abc.abstractmethod
  def datasets(self) -> List[base_input.BaseInputParams]:
    """Returns the list of dataset parameters."""

  @abc.abstractmethod
  def task(self) -> InstantiableParams:
    """Returns the task parameters."""
