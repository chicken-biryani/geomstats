"""Unit tests for the vector space of symmetric matrices."""

import math
import warnings

import tests.helper as helper

import geomstats.backend as gs
import geomstats.tests
from geomstats.geometry.lower_triangular_matrices import LowerTriangularMatrices


class TestLowerTriangularMatrices(geomstats.tests.TestCase):
    """Test of LowerTriangularMatrices methods."""

    def setUp(self):
        """Set up the test."""
        warnings.simplefilter('ignore', category=ImportWarning)

        gs.random.seed(1234)

        self.n = 3
        self.space = LowerTriangularMatrices(self.n)

    def test_belongs(self):
        """Test of belongs method."""
        mats = gs.array(
            [[1., 0.], [-1., 3.]])
        result = LowerTriangularMatrices(2).belongs(mats)
        expected = True
        self.assertAllClose(result, expected)

        mats = gs.array(
            [[1., -1.], [-1., 3.]])
        result = LowerTriangularMatrices(2).belongs(mats)
        expected = False
        self.assertAllClose(result, expected)

        mats = gs.array(
            [[-1., 0.], [0., -3.]])
        result = LowerTriangularMatrices(2).belongs(mats)
        expected = True
        self.assertAllClose(result, expected)

        mats = gs.eye(3)
        result = LowerTriangularMatrices(2).belongs(mats)
        expected = False
        self.assertAllClose(result, expected)

    def test_belongs_vectorization(self):
        """Test of belongs method."""
        mats_2dim = gs.array([
            [[1., 0], [0, 1.]],
            [[1., 2.], [2., 1.]],
            [[-1., 0.], [1., 1.]],
            [[0., 0.], [1., 1.]]])

        mats_3dim = gs.array([
            [[1., 0., 1.0], [0., 1., 0.0], [0., 0., 1.0 ]],
            [[0., 0., 0.0], [2., 1., 0.0], [0., 0., 1.0 ]],
            [[1., 0., 0.0], [2., 1., 0.0], [0., 0., 1.0 ]],
            [[-1., 0., 0.0], [2., 1., 0.0], [0., 0., 1.0 ]]])

        result = LowerTriangularMatrices(2).belongs(mats_2dim)
        expected = gs.array([True, False, True, True])
        self.assertAllClose(result, expected)

        result = LowerTriangularMatrices(3).belongs(mats_3dim)
        expected = gs.array([False, True, True, True])
        self.assertAllClose(result, expected)

    def test_random_point_and_belongs(self):
        """Test of random_point and belongs methods."""
        point = self.space.random_point()
        result = self.space.belongs(point)
        expected = True
        self.assertAllClose(result, expected)

    def test_random_point_and_belongs_vectorization(self):
        """Test of random_point and belongs methods."""
        points = self.space.random_point(4)
        result = self.space.belongs(points)
        expected = gs.array([True] * 4)
        self.assertAllClose(result, expected)

    def test_to_vec_and_from_vec(self):
        """Test for matrix to vector and vector to matrix conversions."""
        chol_mat_1 = gs.array([[1., 0., 0.],
                              [0.6, 7., 0.0],
                              [-3., 0., 8.]])
        vector_1 = self.space.to_vector(chol_mat_1)
        result_1 = self.space.from_vector(vector_1)
        expected_1 = chol_mat_1
        self.assertTrue(gs.allclose(result_1, expected_1))

        chol_mat_1 = gs.array([[1., 0., 1.0],
                              [0.6, 7., 0.0],
                              [-3., 0., 8.]])
        vector_1 = self.space.to_vector(chol_mat_1)
        result_1 = self.space.from_vector(vector_1)
        expected_1 = chol_mat_1
        self.assertTrue(gs.allclose(result_1, expected_1))

        vector_2 = gs.array([1., 2., 3., 4., 5., 6.])
        chol_mat_2 = self.space.from_vector(vector_2)
        result_2 = self.space.to_vector(chol_mat_2)
        expected_2 = vector_2

        self.assertTrue(gs.allclose(result_2, expected_2))

    def test_to_vec_and_from_vec_vectorization(self):
        """Test of vectorization."""
        n_samples = self.n_samples
        vector = gs.random.rand(n_samples, 6)
        chol_mat = self.space.from_vector(vector)
        result = self.space.to_vector(chol_mat)
        expected = vector

        self.assertTrue(gs.allclose(result, expected))

        chol_mat = self.space.random_point(n_samples)
        vector = self.space.to_vector(chol_mat)
        result = self.space.from_vector(vector)
        expected = chol_mat

        self.assertTrue(gs.allclose(result, expected))