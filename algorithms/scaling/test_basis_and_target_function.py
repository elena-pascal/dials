"""
Test for the basis function and target function module.
"""
import copy
import numpy as np
import pytest
from mock import Mock, MagicMock
from scitbx import sparse
from libtbx import phil
from libtbx.test_utils import approx_equal
from dxtbx.model.experiment_list import ExperimentList
from dxtbx.model import Crystal, Scan, Beam, Goniometer, Detector, Experiment
from dials.array_family import flex
from dials.util.options import OptionParser
from dials.algorithms.scaling.scaling_library import create_scaling_model
from dials.algorithms.scaling.scaler_factory import create_scaler
from dials.algorithms.scaling.target_function import ScalingTarget, \
  ScalingTargetFixedIH
from dials.algorithms.scaling.basis_functions import basis_function
from dials.algorithms.scaling.parameter_handler import \
  scaling_active_parameter_manager
from dials.algorithms.scaling.active_parameter_managers import \
  multi_active_parameter_manager
from dials.algorithms.scaling.model.components.scale_components import \
  SingleBScaleFactor, SingleScaleFactor

@pytest.fixture
def large_reflection_table():
  """Create a larger reflection table"""
  return generated_10_refl()

@pytest.fixture
def small_reflection_table():
  """Create a small reflection table"""
  return generated_refl()

def generated_10_refl():
  """Generate reflection table to test the basis and target function."""
  #these miller_idx/d_values don't make physical sense, but I didn't want to
  #have to write the tests for lots of reflections.
  reflections = flex.reflection_table()
  reflections['intensity.prf.value'] = flex.double([75.0, 10.0, 100.0, 25.0, 50.0, 100.0,
    25.0, 20.0, 300.0, 10.0])
  reflections['intensity.prf.variance'] = flex.double([50.0, 10.0, 100.0, 50.0, 10.0, 100.0,
    50.0, 10.0, 100.0, 10.0])
  reflections['miller_index'] = flex.miller_index([(1, 0, 0), (0, 0, 1),
    (1, 0, 0), (1, 0, 0), (0, 0, 1),
    (1, 0, 0), (0, 4, 0), (0, 0, 1),
    (1, 0, 0), (0, 4, 0)]) #don't change
  reflections['d'] = flex.double([2.0, 0.8, 2.0, 2.0, 0.8, 2.0, 2.0, 0.8, 2.0, 1.0]) #don't change
  reflections['lp'] = flex.double(10, 1.0)
  reflections['dqe'] = flex.double(10, 1.0)
  reflections['partiality'] = flex.double(10, 1.0)
  reflections['xyzobs.px.value'] = flex.vec3_double([(0.0, 0.0, 0.0),
    (0.0, 0.0, 5.0), (0.0, 0.0, 10.0), (0.0, 0.0, 15.0), (0.0, 0.0, 20.0),
    (0.0, 0.0, 25.0), (0.0, 0.0, 30.0), (0.0, 0.0, 35.0), (0.0, 0.0, 40.0),
    (0.0, 0.0, 59.0)])
  reflections['s1'] = flex.vec3_double([(0.0, 0.1, 1.0), (0.0, 0.1, 1.0),
    (0.0, 0.1, 20.0), (0.0, 0.1, 20.0), (0.0, 0.1, 20.0), (0.0, 0.1, 20.0),
    (0.0, 0.1, 20.0), (0.0, 0.1, 20.0), (0.0, 0.1, 20.0), (0.0, 0.1, 20.0)])
  reflections.set_flags(flex.bool(10, True), reflections.flags.integrated)
  return [reflections]

def generated_refl():
  """Generate reflection table to test the basis and target function."""
  #these miller_idx/d_values don't make physical sense, but I didn't want to
  #have to write the tests for lots of reflections.
  reflections = flex.reflection_table()
  reflections['intensity.prf.value'] = flex.double([75.0, 10.0, 100.0])
  reflections['intensity.prf.variance'] = flex.double([50.0, 10.0, 100.0])
  reflections['miller_index'] = flex.miller_index([(1, 0, 0), (0, 0, 1),
    (1, 0, 0)]) #don't change
  reflections['d'] = flex.double([2.0, 0.8, 2.0]) #don't change
  reflections['lp'] = flex.double([1.0, 1.0, 1.0])
  reflections['dqe'] = flex.double([1.0, 1.0, 1.0])
  reflections['partiality'] = flex.double([1.0, 1.0, 1.0])
  reflections['xyzobs.px.value'] = flex.vec3_double([(0.0, 0.0, 0.0),
    (0.0, 0.0, 5.0), (0.0, 0.0, 10.0)])
  reflections['s1'] = flex.vec3_double([(0.0, 0.1, 1.0), (0.0, 0.1, 1.0),
    (0.0, 0.1, 20.0)])
  reflections.set_flags(flex.bool([True, True, True]),
    reflections.flags.integrated)
  return [reflections]

#@pytest.fixture(scope='module')
def generated_single_exp():
  """Generate an experiment object."""
  experiments = ExperimentList()
  exp_dict = {"__id__" : "crystal", "real_space_a": [1.0, 0.0, 0.0],
              "real_space_b": [0.0, 1.0, 0.0], "real_space_c": [0.0, 0.0, 2.0],
              "space_group_hall_symbol": " C 2y"}
  crystal = Crystal.from_dict(exp_dict)
  scan = Scan(image_range=[0, 60], oscillation=[0.0, 1.0])
  beam = Beam(s0=(0.0, 0.0, 1.01))
  goniometer = Goniometer((1.0, 0.0, 0.0))
  detector = Detector()
  experiments.append(Experiment(beam=beam, scan=scan, goniometer=goniometer,
    detector=detector, crystal=crystal))
  return experiments

def generated_param(model='KB'):
  """Generate the scaling phil param scope."""
  phil_scope = phil.parse('''
      include scope dials.algorithms.scaling.scaling_options.phil_scope
  ''', process_includes=True)

  optionparser = OptionParser(phil=phil_scope, check_format=False)
  parameters, _ = optionparser.parse_args(args=[], quick_parse=True,
    show_diff_phil=False)
  parameters.__inject__('model', model)
  parameters.parameterisation.absorption_term = False
  return parameters

@pytest.fixture
def single_exp():
  """Create an experimentlist with a single experiment."""
  return generated_single_exp()

@pytest.fixture
def KB_param():
  """Create a KB model params object."""
  return generated_param(model='KB')

@pytest.fixture
def physical_param():
  """Create a physical model params object."""
  return generated_param(model='physical')

@pytest.fixture
def mock_single_Ih_table():
  """Mock Ih table to use for testing the target function."""
  Ih_table = Mock()
  Ih_table.inverse_scale_factors = flex.double([1.0, 1.0/1.1, 1.0])
  Ih_table.intensities = flex.double([10.0, 10.0, 12.0])
  Ih_table.Ih_values = flex.double([11.0, 11.0, 11.0])
  # These values should give residuals of [-1.0, 0.0, 1.0]
  Ih_table.weights = flex.double([1.0, 1.0, 1.0])
  Ih_table.size = 3
  Ih_table.derivatives = sparse.matrix(3, 1)
  Ih_table.derivatives[0, 0] = 1.0
  Ih_table.derivatives[1, 0] = 2.0
  Ih_table.derivatives[2, 0] = 3.0
  return Ih_table

@pytest.fixture()
def mock_Ih_table(mock_single_Ih_table):
  Ih_table = MagicMock()
  Ih_table.blocked_data_list = [mock_single_Ih_table]
  Ih_table.free_Ih_table = None
  return Ih_table

'''@pytest.fixture()
def mock_Ih_table_with_free():
  """Mock Ih table with a copy set as the free Ih table."""
  Ih_table = mock_Ih_table()
  Ih_table.free_Ih_table = mock_Ih_table()
  return Ih_table

@pytest.fixture
def mock_single_scaler(mock_Ih_table_with_free):
  """Mock single scaler instance."""
  scaler = Mock()
  scaler.Ih_table = mock_Ih_table_with_free
  return scaler'''

@pytest.fixture
def mock_apm():
  """A mock apm object to hold the derivatives."""
  apm = MagicMock()
  apm.derivatives = sparse.matrix(3, 1)
  apm.derivatives[0, 0] = 1.0
  apm.derivatives[1, 0] = 2.0
  apm.derivatives[2, 0] = 3.0
  apm.n_obs = 3
  apm.n_active_params = 1
  apm.x = flex.double([1.0])
  return apm

@pytest.fixture
def mock_multiapm(mock_apm):
  """Create a mock-up of the multi apm for testing."""
  apm = MagicMock()
  apm.apm_list = [mock_apm, mock_apm]
  apm.apm_data = {0 : {'start_idx' : 0}, 1: {'start_idx' : 1}}
  apm.n_active_params = len(apm.apm_list)
  return apm

def test_basis_function(small_reflection_table):
  """Test for the basis function class. This calculates scale factors and
  derivatives for reflections based on the model components."""

  # To test the basis function, need a scaling active parameter manager - to set
  # this up we need a components dictionary with some reflection data.

  # Let's use KB model components for simplicity.
  rt = small_reflection_table[0]
  components = {'scale' : SingleScaleFactor(flex.double([1.0])), 'decay':
    SingleBScaleFactor(flex.double([0.0]))} #Create empty components.
  for component in components.itervalues():
    component.update_reflection_data(rt) #Add some data to components.

  apm = scaling_active_parameter_manager(components, ['decay', 'scale'])

  # First test that scale factors can be successfully updated.
  # Manually change the parameters in the apm.
  decay = components['decay'] # Define alias
  scale = components['scale'] # Define alias
  # Note, order of params in apm.x depends on order in scaling model components.
  new_B = 1.0
  new_S = 2.0
  apm.set_param_vals(flex.double([new_S, new_B]))
  basis_fn = basis_function(curvatures=True)
  basis_fn.update_scale_factors(apm)

  # Now test that the inverse scale factor is correctly calculated.
  calculated_sfs = basis_fn.calculate_scale_factors(apm)[0]
  assert list(calculated_sfs) == list(new_S * np.exp(new_B/
    (2.0*(decay.d_values[0]**2))))

  # Now check that the derivative matrix is correctly calculated.
  calc_derivs = basis_fn.calculate_derivatives(apm)[0]
  assert calc_derivs[0, 0] == scale.derivatives[0][0, 0] * decay.inverse_scales[0][0]
  assert calc_derivs[1, 0] == scale.derivatives[0][1, 0] * decay.inverse_scales[0][1]
  assert calc_derivs[2, 0] == scale.derivatives[0][2, 0] * decay.inverse_scales[0][2]
  assert calc_derivs[0, 1] == decay.derivatives[0][0, 0] * scale.inverse_scales[0][0]
  assert calc_derivs[1, 1] == decay.derivatives[0][1, 0] * scale.inverse_scales[0][1]
  assert calc_derivs[2, 1] == decay.derivatives[0][2, 0] * scale.inverse_scales[0][2]

  # Test that the curvatures matrix is correctly composed.
  calc_curvs = basis_fn.calculate_curvatures(apm)[0]
  assert calc_curvs[0, 0] == scale.curvatures[0][0, 0] * decay.inverse_scales[0][0]
  assert calc_curvs[1, 0] == scale.curvatures[0][1, 0] * decay.inverse_scales[0][1]
  assert calc_curvs[2, 0] == scale.curvatures[0][2, 0] * decay.inverse_scales[0][2]
  assert calc_curvs[0, 1] == decay.curvatures[0][0, 0] * scale.inverse_scales[0][0]
  assert calc_curvs[1, 1] == decay.curvatures[0][1, 0] * scale.inverse_scales[0][1]
  assert calc_curvs[2, 1] == decay.curvatures[0][2, 0] * scale.inverse_scales[0][2]

  # Repeat the test when there is only one active parameter.
  # First reset the parameters
  components['decay'].parameters = flex.double([0.0])
  components['scale'].parameters = flex.double([1.0])
  components['decay'].calculate_scales_and_derivatives()
  components['scale'].calculate_scales_and_derivatives()

  # Now generate a parameter manager for a single component.
  apm = scaling_active_parameter_manager(components, ['scale'])
  new_S = 2.0
  apm.set_param_vals(flex.double(components['scale'].n_params, new_S))
  basis_fn = basis_function().calculate_scales_and_derivatives(apm)
  #basis_fn = basis_func.calculate_scales_and_derivatives() # All in one alternative call.

  # Test that the scales and derivatives were correctly calculated
  assert list(basis_fn[0][0]) == list([new_S] *
    components['scale'].inverse_scales[0].size())
  assert basis_fn[1][0][0, 0] == components['scale'].derivatives[0][0, 0]
  assert basis_fn[1][0][1, 0] == components['scale'].derivatives[0][1, 0]
  assert basis_fn[1][0][2, 0] == components['scale'].derivatives[0][2, 0]

  apm = scaling_active_parameter_manager(components, [])
  basis_fn = basis_function(curvatures=True)
  _, d, c = basis_fn.calculate_scales_and_derivatives(apm)
  assert d is None
  assert c is None

# For testing the targetfunction, need a real scaler instance and apm as
# update_for_minimisation creates a strong binding between these objects.

def test_finite_difference_gradient(small_reflection_table, single_exp, physical_param):
  # Need to initialise a scaler - then get an apm for parameters, then a target
  # function for calculating gradient. Then check this against finite difference - 
  # which should also mimic update for minimisation?
  (test_reflections, test_experiments, params) = (
    small_reflection_table, single_exp, physical_param)
  assert len(test_experiments) == 1
  assert len(test_reflections) == 1
  experiments = create_scaling_model(params, test_experiments, test_reflections)
  scaler = create_scaler(params, experiments, test_reflections)
  assert scaler.experiments.scaling_model.id_ == 'physical'

  # Initialise the parameters and create an apm
  #scaler.components['scale'].parameters = flex.double([2.0])
  #scaler.components['decay'].parameters = flex.double([0.0])
  scaler.components['scale'].inverse_scales = flex.double([2.0, 1.0, 2.0])
  scaler.components['decay'].inverse_scales = flex.double([1.0, 1.0, 0.4])
  apm = multi_active_parameter_manager([scaler.components],
    [['scale', 'decay']], scaling_active_parameter_manager)

  # Now do finite difference check.

  target = ScalingTarget()
  scaler.update_for_minimisation(apm)
  grad = target.calculate_gradients(scaler.Ih_table.blocked_data_list[0])
  res = target.calculate_residuals(scaler.Ih_table.blocked_data_list[0])

  assert res > 1e-8, """residual should not be zero, or the gradient test
    below will not really be working!"""

  # Now compare to finite difference
  f_d_grad = calculate_gradient_fd(target, scaler, apm)
  print(list(f_d_grad))
  print(list(grad))
  assert approx_equal(list(grad), list(f_d_grad))

  sel = f_d_grad > 1e-8
  assert sel, """assert sel has some elements, as finite difference grad should
    not all be zero, or the test will not really be working!
    (expect one to be zero for KB scaling example?)"""

def test_target_function(small_reflection_table, single_exp, KB_param):
  """Test for the ScalingTarget class."""

  # First set up the scaler
  (test_reflections, test_experiments, params) = (
    small_reflection_table, single_exp, KB_param)
  assert len(test_experiments) == 1
  assert len(test_reflections) == 1
  experiments = create_scaling_model(params, test_experiments, test_reflections)
  scaler = create_scaler(params, experiments, test_reflections)
  assert scaler.experiments.scaling_model.id_ == 'KB'

  # Initialise the parameters and create an apm
  scaler.components['scale'].parameters = flex.double([2.0])
  scaler.components['decay'].parameters = flex.double([0.0])
  scaler.components['scale'].inverse_scales = flex.double([2.0, 2.0, 2.0])
  scaler.components['decay'].inverse_scales = flex.double([1.0, 1.0, 1.0])
  apm = multi_active_parameter_manager([scaler.components],
    [['scale', 'decay']], scaling_active_parameter_manager)
  scaler.update_for_minimisation(apm)

  # Create a scaling target and check gradients
  target = ScalingTarget(scaler, apm)

  # Below methods needed for refinement engine calls
  Ih_table = scaler.Ih_table.blocked_data_list[0]
  _ = target.compute_restraints_residuals_and_gradients(apm)
  _ = target.compute_residuals_and_gradients(Ih_table)
  _ = target.compute_residuals(Ih_table)
  _ = target.compute_functional_gradients(Ih_table)
  _ = target.achieved()

  resid = target.calculate_residuals(Ih_table)**2 * \
    scaler.Ih_table.blocked_data_list[0].weights
  # Note - activate two below when curvatures are implemented.
  #_ = target.compute_restraints_functional_gradients_and_curvatures()
  #_ = target.compute_functional_gradients_and_curvatures()

  # Calculate residuals explicitly and check RMSDS.
  assert approx_equal(list(resid), [0.0, 50.0/36.0, 100.0/36.0])
  assert approx_equal(target.rmsds(scaler.Ih_table, apm)[0],
    (150.0/(36.0*3.0))**0.5)

def test_target_jacobian_calc(physical_param, single_exp, large_reflection_table):
  """Test for the target function calculation of the jacobian matrix."""
  test_params, exp, test_refl = physical_param, single_exp, large_reflection_table
  test_params.parameterisation.decay_term = False
  experiments = create_scaling_model(test_params, exp, test_refl)
  assert experiments[0].scaling_model.id_ == 'physical'
  scaler = create_scaler(test_params, experiments, test_refl)

  apm = multi_active_parameter_manager([scaler.components], [['scale']],
    scaling_active_parameter_manager)

  target = ScalingTarget()
  scaler.update_for_minimisation(apm)

  fd_jacobian = calculate_jacobian_fd(target,
    scaler, apm)
  _, jacobian, _ = target.compute_residuals_and_gradients(
    scaler.Ih_table.blocked_data_list[0])

  n_rows = jacobian.n_rows
  n_cols = jacobian.n_cols

  print(jacobian)
  print(fd_jacobian)

  for i in range(0, n_rows):
    for j in range(0, n_cols):
      assert jacobian[i, j] == pytest.approx(fd_jacobian[i, j], abs=1e-4)

def test_target_jacobian_calc_splitblocks(physical_param, single_exp,
  large_reflection_table):
  """Test for the target function calculation of the jacobian matrix."""
  test_params, exp, test_refl = physical_param, single_exp, large_reflection_table
  test_params.scaling_options.nproc = 2
  test_params.parameterisation.decay_term = False
  experiments = create_scaling_model(test_params, exp, test_refl)
  assert experiments[0].scaling_model.id_ == 'physical'
  scaler = create_scaler(test_params, experiments, test_refl)

  apm = multi_active_parameter_manager([scaler.components], [['scale']],
    scaling_active_parameter_manager)

  target = ScalingTarget(scaler, apm)
  scaler.update_for_minimisation(apm)

  for i, block in enumerate(scaler.Ih_table.blocked_data_list):
    fd_jacobian = calculate_jacobian_fd(target, scaler, apm, block_id=i)
    _, jacobian, _ = target.compute_residuals_and_gradients(block)
    n_rows = max(fd_jacobian.n_rows, jacobian.n_rows)
    n_cols = max(fd_jacobian.n_cols, jacobian.n_cols)
    for i in range(0, n_rows):
      for j in range(0, n_cols):
        assert jacobian[i, j] == pytest.approx(fd_jacobian[i, j], abs=1e-4)

def test_target_fixedIh(mock_multiapm, mock_Ih_table):
  """Test the target function for targeted scaling (where Ih is fixed)."""

  target = ScalingTargetFixedIH()
  Ih_table = mock_Ih_table.blocked_data_list[0]
  R, _ = target.compute_residuals(Ih_table)
  expected_residuals = flex.double([-1.0, 0.0, 1.0])
  assert list(R) == list(expected_residuals)
  _, G = target.compute_functional_gradients(Ih_table)
  assert list(G) == [-44.0]
  # Add in finite difference check

  J = target.calculate_jacobian(Ih_table)
  assert J.n_cols == 1
  assert J.n_rows == 3
  assert J.non_zeroes == 3
  assert J[0, 0] == -11.0
  assert J[1, 0] == -22.0
  assert J[2, 0] == -33.0

  expected_rmsd = (expected_residuals**2 / len(expected_residuals))**0.5
  assert target._rmsds is None
  target._rmsds = []
  target.rmsds(mock_Ih_table, mock_multiapm)
  assert target._rmsds == pytest.approx([expected_rmsd])

def calculate_gradient_fd(target, scaler, apm):
  """Calculate gradient array with finite difference approach."""
  delta = 1.0e-6
  gradients = flex.double([0.0] * apm.n_active_params)
  Ih_table = scaler.Ih_table.blocked_data_list[0]
  #iterate over parameters, varying one at a time and calculating the gradient
  for i in range(apm.n_active_params):
    new_x = copy.copy(apm.x)
    new_x[i] -= 0.5 * delta
    #target.apm.x[i] -= 0.5 * delta
    apm.set_param_vals(new_x)
    scaler.update_for_minimisation(apm)
    R_low = (target.calculate_residuals(Ih_table)**2) * Ih_table.weights
    #target.apm.x[i] += delta
    new_x[i] += delta
    apm.set_param_vals(new_x)
    scaler.update_for_minimisation(apm)
    R_upper = (target.calculate_residuals(Ih_table)**2) * Ih_table.weights
    #target.apm.x[i] -= 0.5 * delta
    new_x[i] -= 0.5 * delta
    apm.set_param_vals(new_x)
    scaler.update_for_minimisation(apm)
    gradients[i] = (flex.sum(R_upper) - flex.sum(R_low)) / delta
  return gradients

def calculate_jacobian_fd(target, scaler, apm, block_id=0):
  """Calculate jacobian matrix with finite difference approach."""
  delta = 1.0e-8
  #apm = target.apm
  jacobian = sparse.matrix(scaler.Ih_table.blocked_data_list[block_id].size,
    apm.n_active_params)
  Ih_table = scaler.Ih_table.blocked_data_list[block_id]
  #iterate over parameters, varying one at a time and calculating the residuals
  for i in range(apm.n_active_params):
    new_x = copy.copy(apm.x)
    new_x[i] -= 0.5 * delta
    apm.set_param_vals(new_x)
    scaler.update_for_minimisation(apm)
    R_low = target.calculate_residuals(Ih_table)#unweighted unsquared residual
    new_x[i] += delta
    apm.set_param_vals(new_x)
    scaler.update_for_minimisation(apm)
    R_upper = target.calculate_residuals(Ih_table) #unweighted unsquared residual
    new_x[i] -= 0.5 * delta
    apm.set_param_vals(new_x)
    scaler.update_for_minimisation(apm)
    fin_difference = (R_upper - R_low) / delta
    for j in range(fin_difference.size()):
      jacobian[j, i] = fin_difference[j]
  return jacobian
