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
"""Tests for Learners."""
from absl import logging
from absl.testing import absltest
from absl.testing import parameterized
from jax import numpy as jnp
from jax import test_util
from lingvo.jax import base_layer
from lingvo.jax import learners
from lingvo.jax import optimizers
from lingvo.jax import py_utils
from lingvo.jax import schedules
import numpy as np
import tensorflow.compat.v2 as tf

NestedMap = py_utils.NestedMap


class LearnersTest(test_util.JaxTestCase):

  @parameterized.parameters(
      (0.5, 0.5, 1.5, 1., 0.),
      (0., 0., 1.5, 1., 0.),
      (0.5, 0.5, 1.5, 0., 1.),
      (0., 0., 1.5, 0., 1.),
  )
  def test_learner_clip_gradients(self, g1a, g1b, g2, global_clip_norm,
                                  single_clip_norm):
    learner_p = learners.Learner.Params()
    learner_p.name = 'learner'
    learner_p.loss_name = 'loss'
    learner_p.optimizer = optimizers.Sgd.Params()
    learner_p.optimizer.learning_rate = 1.
    learner_p.optimizer.lr_schedule = schedules.Constant.Params()
    if global_clip_norm:
      learner_p.optimizer.clip_gradient_norm_to_value = global_clip_norm
    elif single_clip_norm:
      learner_p.optimizer.clip_gradient_single_norm_to_value = single_clip_norm

    learner_instance = learner_p.Instantiate()

    grads = NestedMap(
        grad1=jnp.array([g1a, g1b], dtype=jnp.float32),
        grad2=jnp.array([g2], dtype=jnp.float32))

    with base_layer.JaxContext.new_context():
      transformed_grads = learner_instance.scale_gradients(grads)

    global_norm = np.linalg.norm([g1a, g1b, g2])
    local_norm1 = np.linalg.norm([g1a, g1b])
    local_norm2 = np.linalg.norm([g2])
    if global_clip_norm:
      gn1a = g1a * global_clip_norm / max(global_norm, global_clip_norm)
      gn1b = g1b * global_clip_norm / max(global_norm, global_clip_norm)
      gn2 = g2 * global_clip_norm / max(global_norm, global_clip_norm)
    elif single_clip_norm:
      gn1a = g1a * single_clip_norm / max(local_norm1, single_clip_norm)
      gn1b = g1b * single_clip_norm / max(local_norm1, single_clip_norm)
      gn2 = g2 * single_clip_norm / max(local_norm2, single_clip_norm)
    expected_grad1 = jnp.array([gn1a, gn1b], dtype=jnp.float32)
    expected_grad2 = jnp.array([gn2], dtype=jnp.float32)

    self.assertAllClose(expected_grad1, transformed_grads.grad1)
    self.assertAllClose(expected_grad2, transformed_grads.grad2)

  @parameterized.parameters(
      (0.5, 2.0, True),
      (1.5, 3.0, False),
      (10., 0.1, True),
      (100., 2.0, False),
  )
  def test_multioptimizer_learner(self, lr_multiplier1, lr_multiplier2,
                                  use_vq_ngrams):
    learner_p = learners.MultiOptimizerLearner.Params()
    learner_p.name = 'learner'
    learner_p.loss_name = 'loss'
    learner_p.optimizer = optimizers.Sgd.Params()
    learner_p.optimizer.learning_rate = 1.
    learner_p.optimizer.lr_schedule = schedules.Constant.Params()
    aux_p1 = optimizers.Sgd.Params()
    aux_p1.lr_schedule = schedules.Constant.Params()
    aux_p1.learning_rate = lr_multiplier1
    aux_p2 = optimizers.Sgd.Params()
    aux_p2.lr_schedule = schedules.Constant.Params()
    aux_p2.learning_rate = lr_multiplier2

    learner_p.auxiliary_optimizers = [aux_p1, aux_p2]
    learner_p.auxiliary_regex = ['ngram', 'transformer']
    learner_instance = learner_p.Instantiate()

    grads = NestedMap()
    grads.lm = NestedMap()
    grads.lm.ngrammer = NestedMap()
    old_vars = grads.DeepCopy()
    emb_var1 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    emb_var2 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    grad1 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    grad2 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    if use_vq_ngrams:
      grads.lm.ngrammer.ngram_layer = NestedMap()
      grads.lm.ngrammer.ngram_layer.ngram_table = [
          NestedMap(emb_var=grad1),
          NestedMap(emb_var=grad2)
      ]
      old_vars.lm.ngrammer.ngram_layer = NestedMap()
      old_vars.lm.ngrammer.ngram_layer.ngram_table = [
          NestedMap(emb_var=emb_var1),
          NestedMap(emb_var=emb_var2)
      ]
    else:
      grads.lm.ngrammer.ngram_table = [
          NestedMap(emb_var=grad1),
          NestedMap(emb_var=grad2)
      ]
      old_vars.lm.ngrammer.ngram_table = [
          NestedMap(emb_var=emb_var1),
          NestedMap(emb_var=emb_var2)
      ]
    # Create some other keys.
    grads.lm.transformer = NestedMap(
        w=jnp.asarray(np.random.normal(1.4, 2.0, [4, 4]).astype('float32')))
    old_vars.lm.transformer = NestedMap(
        w=jnp.asarray(np.random.normal(1.2, 4.0, [4, 4]).astype('float32')))
    grads.lm.ffn = NestedMap(
        k=jnp.asarray(np.random.normal(1.6, 2.0, [4, 4]).astype('float32')))
    old_vars.lm.ffn = NestedMap(
        k=jnp.asarray(np.random.normal(1.3, 2.0, [4, 4]).astype('float32')))
    grad_tx = learner_instance.get_grad_tx(mdl_vars=old_vars)
    opt_states = grad_tx.init(old_vars)
    with base_layer.JaxContext.new_context():
      transformed_grads, _ = learner_instance.update_states(
          grads, opt_states, old_vars)

    expected_grad1 = -lr_multiplier1 * grad1
    expected_grad2 = -lr_multiplier1 * grad2
    if use_vq_ngrams:
      new_grad1 = (
          transformed_grads.lm.ngrammer.ngram_layer.ngram_table[0].emb_var)
      new_grad2 = (
          transformed_grads.lm.ngrammer.ngram_layer.ngram_table[1].emb_var)
    else:
      new_grad1 = transformed_grads.lm.ngrammer.ngram_table[0].emb_var
      new_grad2 = transformed_grads.lm.ngrammer.ngram_table[1].emb_var
    self.assertAllClose(new_grad1, expected_grad1)
    self.assertAllClose(new_grad2, expected_grad2)
    expected_grad_transformer = -lr_multiplier2 * grads.lm.transformer.w
    new_grad_transformer = transformed_grads.lm.transformer.w
    expected_grad_ffn = -grads.lm.ffn.k
    new_grad_ffn = transformed_grads.lm.ffn.k
    self.assertAllClose(new_grad_transformer, expected_grad_transformer)
    self.assertAllClose(new_grad_ffn, expected_grad_ffn)

  def test_multioptimizer_learner_adam_adagrad(self):
    learner_p = learners.MultiOptimizerLearner.Params()
    learner_p.name = 'learner'
    learner_p.loss_name = 'loss'
    learner_p.optimizer = optimizers.Adam.ParamsA()
    learner_p.optimizer.learning_rate = 1.
    learner_p.optimizer.lr_schedule = schedules.Constant.Params()
    aux_p1 = optimizers.Adam.ParamsA()
    aux_p1.lr_schedule = schedules.Constant.Params()
    aux_p1.learning_rate = 2.0
    aux_p2 = optimizers.Adagrad.Params()
    aux_p2.lr_schedule = schedules.Constant.Params()
    aux_p2.learning_rate = 3.0

    learner_p.auxiliary_optimizers = [aux_p1, aux_p2]
    learner_p.auxiliary_regex = ['ngram', 'transformer']
    learner_instance = learner_p.Instantiate()

    grads = NestedMap()
    grads.lm = NestedMap()
    grads.lm.ngrammer = NestedMap()
    old_vars = grads.DeepCopy()
    emb_var1 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    emb_var2 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    grad1 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    grad2 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    grads.lm.ngrammer.ngram_table = [
        NestedMap(emb_var=grad1),
        NestedMap(emb_var=grad2)
    ]
    old_vars.lm.ngrammer.ngram_table = [
        NestedMap(emb_var=emb_var1),
        NestedMap(emb_var=emb_var2)
    ]
    # Create some other keys.
    grads.lm.transformer = NestedMap(
        w=jnp.asarray(np.random.normal(1.4, 2.0, [4, 4]).astype('float32')))
    old_vars.lm.transformer = NestedMap(
        w=jnp.asarray(np.random.normal(1.2, 4.0, [4, 4]).astype('float32')))
    grads.lm.ffn = NestedMap(
        k=jnp.asarray(np.random.normal(1.6, 2.0, [4, 4]).astype('float32')))
    old_vars.lm.ffn = NestedMap(
        k=jnp.asarray(np.random.normal(1.3, 2.0, [4, 4]).astype('float32')))
    grad_tx = learner_instance.get_grad_tx(mdl_vars=old_vars)
    opt_states = grad_tx.init(old_vars)
    logging.info('opt_states: %s', opt_states)

  def test_multioptimizer_learner_value_error(self):
    learner_p = learners.MultiOptimizerLearner.Params()
    learner_p.name = 'learner'
    learner_p.loss_name = 'loss'
    learner_p.optimizer = optimizers.Adam.ParamsA()
    learner_p.optimizer.learning_rate = 1.
    learner_p.optimizer.lr_schedule = schedules.Constant.Params()
    aux_p1 = optimizers.Adam.ParamsA()
    aux_p1.lr_schedule = schedules.Constant.Params()
    aux_p1.learning_rate = 2.0
    aux_p2 = optimizers.Adagrad.Params()
    aux_p2.lr_schedule = schedules.Constant.Params()
    aux_p2.learning_rate = 3.0

    learner_p.auxiliary_optimizers = [aux_p1, aux_p2]
    learner_p.auxiliary_regex = ['ngrammer', 'ngram']
    learner_instance = learner_p.Instantiate()

    grads = NestedMap()
    grads.lm = NestedMap()
    grads.lm.ngrammer = NestedMap()
    old_vars = grads.DeepCopy()
    emb_var1 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    emb_var2 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    grad1 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    grad2 = jnp.asarray(np.random.normal(1.0, 0.5, [4, 8]).astype('float32'))
    grads.lm.ngrammer.ngram_table = [
        NestedMap(emb_var=grad1),
        NestedMap(emb_var=grad2)
    ]
    old_vars.lm.ngrammer.ngram_table = [
        NestedMap(emb_var=emb_var1),
        NestedMap(emb_var=emb_var2)
    ]
    # Create some other keys.
    grads.lm.transformer = NestedMap(
        w=jnp.asarray(np.random.normal(1.4, 2.0, [4, 4]).astype('float32')))
    old_vars.lm.transformer = NestedMap(
        w=jnp.asarray(np.random.normal(1.2, 4.0, [4, 4]).astype('float32')))
    grads.lm.ffn = NestedMap(
        k=jnp.asarray(np.random.normal(1.6, 2.0, [4, 4]).astype('float32')))
    old_vars.lm.ffn = NestedMap(
        k=jnp.asarray(np.random.normal(1.3, 2.0, [4, 4]).astype('float32')))
    with self.assertRaises(ValueError):
      learner_instance.get_grad_tx(mdl_vars=old_vars)

  def test_multioptimizer_learner_sharding(self):
    learner_p = learners.MultiOptimizerLearner.Params()
    learner_p.name = 'learner'
    learner_p.loss_name = 'loss'
    learner_p.optimizer = optimizers.ShardedAdafactor.Params()
    learner_p.optimizer.learning_rate = 1.
    learner_p.optimizer.decay_method = 'pow'
    learner_p.optimizer.lr_schedule = schedules.Constant.Params()
    aux_p1 = optimizers.ShardedAdafactor.Params()
    aux_p1.lr_schedule = schedules.Constant.Params()
    aux_p1.learning_rate = 2.0
    aux_p1.decay_method = 'pow'
    aux_p2 = optimizers.ShardedAdafactor.Params()
    aux_p2.lr_schedule = schedules.Constant.Params()
    aux_p2.decay_method = 'adam'
    aux_p2.learning_rate = 3.0

    # Add auxiliary optimizers.
    learner_p.auxiliary_optimizers = [aux_p1, aux_p2]
    learner_p.auxiliary_regex = ['ngrammer', 'transformer']
    learner_instance = learner_p.Instantiate()

    # Add a single instance optimizer.
    learner_p = learners.Learner.Params()
    learner_p.name = 'learner'
    learner_p.loss_name = 'loss'
    learner_p.optimizer = optimizers.ShardedAdafactor.Params()
    learner_p.optimizer.learning_rate = 1.
    learner_p.optimizer.decay_method = 'pow'
    learner_p.optimizer.lr_schedule = schedules.Constant.Params()
    learner_instance_single = learner_p.Instantiate()

    # Define device mesh.
    mesh_shape = [1, 2, 1]
    num_devices = np.prod(mesh_shape)
    logging.info('num_local_devices: %s', num_devices)
    device_mesh = np.arange(num_devices).reshape(mesh_shape)

    grads = NestedMap()
    grads.lm = NestedMap()
    grads.lm.ngrammer = NestedMap()
    old_vars = grads.DeepCopy()
    emb_var1 = py_utils.weight_params(
        shape=[4, 8],
        device_mesh=device_mesh,
        tensor_split_dims_mapping=[-1, 1])
    emb_var2 = py_utils.weight_params(
        shape=[4, 8],
        device_mesh=device_mesh,
        tensor_split_dims_mapping=[-1, 1])
    grad1 = py_utils.weight_params(
        shape=[4, 8],
        device_mesh=device_mesh,
        tensor_split_dims_mapping=[-1, 1])
    grad2 = py_utils.weight_params(
        shape=[4, 8],
        device_mesh=device_mesh,
        tensor_split_dims_mapping=[-1, 1])
    grads.lm.ngrammer.ngram_table = [
        NestedMap(emb_var=grad1),
        NestedMap(emb_var=grad2)
    ]
    old_vars.lm.ngrammer.ngram_table = [
        NestedMap(emb_var=emb_var1),
        NestedMap(emb_var=emb_var2)
    ]
    # Create some other keys.
    grads.lm.transformer = NestedMap(
        w=py_utils.weight_params(
            shape=[4, 8],
            device_mesh=device_mesh,
            tensor_split_dims_mapping=[-1, 1]))
    old_vars.lm.transformer = NestedMap(
        w=py_utils.weight_params(
            shape=[4, 8],
            device_mesh=device_mesh,
            tensor_split_dims_mapping=[-1, 1]))
    grads.lm.ffn = NestedMap(
        k=py_utils.weight_params(
            shape=[4, 8],
            device_mesh=device_mesh,
            tensor_split_dims_mapping=[-1, 1]))
    old_vars.lm.ffn = NestedMap(
        k=py_utils.weight_params(
            shape=[4, 8],
            device_mesh=device_mesh,
            tensor_split_dims_mapping=[0, 1]))

    grad_tx = learner_instance.get_grad_tx(mdl_vars=old_vars)
    grad_tx_single = learner_instance_single.get_grad_tx(mdl_vars=old_vars)
    partition_spec = grad_tx.init_partition_spec(old_vars)
    partition_spec_single = grad_tx_single.init_partition_spec(old_vars)
    for k in partition_spec_single[0]._fields:
      tf.nest.assert_same_structure(
          getattr(partition_spec[0], k), getattr(partition_spec_single[0], k))


if __name__ == '__main__':
  absltest.main()
