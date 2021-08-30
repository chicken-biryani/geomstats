"""Parameterized curves on any given manifold."""

import math

import numpy as np
from scipy.interpolate import CubicSpline

import geomstats.backend as gs
from geomstats.algebra_utils import from_vector_to_diagonal_matrix
from geomstats.geometry.euclidean import Euclidean
from geomstats.geometry.euclidean import EuclideanMetric
from geomstats.geometry.landmarks import L2Metric
from geomstats.geometry.manifold import Manifold
from geomstats.geometry.riemannian_metric import RiemannianMetric
from geomstats.geometry.symmetric_matrices import SymmetricMatrices

R2 = Euclidean(dim=2)
R3 = Euclidean(dim=3)


class DiscreteCurves(Manifold):
    r"""Space of discrete curves sampled at points in ambient_manifold.

    Each individual curve is represented by a 2d-array of shape `[
    n_sampling_points, ambient_dim]`. A Batch of curves can be passed to
    all methods either as a 3d-array if all curves have the same number of
    sampled points, or as a list of 2d-arrays, each representing a curve.

    Parameters
    ----------
    ambient_manifold : Manifold
        Manifold in which curves take values.

    Attributes
    ----------
    ambient_manifold : Manifold
        Manifold in which curves take values.
    l2_metric : callable
        Function that takes as argument an integer number of sampled points
        and returns the corresponding L2 metric (product) metric,
        a RiemannianMetric object
    square_root_velocity_metric : RiemannianMetric
        Square root velocity metric.
    """

    def __init__(self, ambient_manifold):
        super(DiscreteCurves, self).__init__(dim=math.inf)
        self.ambient_manifold = ambient_manifold
        self.l2_metric = lambda n: L2Metric(
            self.ambient_manifold, n_landmarks=n)
        self.square_root_velocity_metric = SRVMetric(self.ambient_manifold)
        self.quotient_square_root_velocity_metric = \
            QuotientSRVMetric(self.ambient_manifold)

    def belongs(self, point, atol=gs.atol):
        """Test whether a point belongs to the manifold.

        Test that all points of the curve belong to the ambient manifold.

        Parameters
        ----------
        point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Point representing a discrete curve.
        atol : float
            Absolute tolerance.
            Optional, default: backend atol.

        Returns
        -------
        belongs : bool
            Boolean evaluating if point belongs to the space of discrete
            curves.
        """
        def each_belongs(pt):
            return gs.all(self.ambient_manifold.belongs(pt))

        if isinstance(point, list) or point.ndim > 2:
            return gs.stack([each_belongs(pt) for pt in point])

        return each_belongs(point)

    def is_tangent(self, vector, base_point, atol=gs.atol):
        """Check whether the vector is tangent at a curve.

        A vector is tangent at a curve if it is a vector field along that
        curve.

        Parameters
        ----------
        vector : array-like, shape=[..., n_sampling_points, ambient_dim]
            Vector.
        base_point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.
        atol : float
            Absolute tolerance.
            Optional, default: backend atol.

        Returns
        -------
        is_tangent : bool
            Boolean denoting if vector is a tangent vector at the base point.
        """
        ambient_manifold = self.ambient_manifold
        shape = vector.shape
        stacked_vec = gs.reshape(vector, (-1, shape[-1]))
        stacked_point = gs.reshape(base_point, (-1, shape[-1]))
        is_tangent = ambient_manifold.is_tangent(
            stacked_vec, stacked_point, atol)
        is_tangent = gs.reshape(is_tangent, shape[:-1])
        return gs.all(is_tangent, axis=-1)

    def to_tangent(self, vector, base_point):
        """Project a vector to a tangent space of the manifold.

        As tangent vectors are vector fields along a curve, each component of
        the vector is projected to the tangent space of the corresponding
        point of the discrete curve. The number of sampling points should
        match in the vector and the base_point.

        Parameters
        ----------
        vector : array-like, shape=[..., n_sampling_points, ambient_dim]
            Vector.
        base_point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.

        Returns
        -------
        tangent_vec : array-like, shape=[..., n_sampling_points, ambient_dim]
            Tangent vector at base point.
        """
        ambient_manifold = self.ambient_manifold
        shape = vector.shape
        stacked_vec = gs.reshape(vector, (-1, shape[-1]))
        stacked_point = gs.reshape(base_point, (-1, shape[-1]))
        tangent_vec = ambient_manifold.to_tangent(stacked_vec, stacked_point)
        tangent_vec = gs.reshape(tangent_vec, vector.shape)
        return tangent_vec

    def random_point(self, n_samples=1, bound=1., n_sampling_points=10):
        """Sample random curves.

        If the ambient manifold is compact, a uniform distribution is used.

        Parameters
        ----------
        n_samples : int
            Number of samples.
            Optional, default: 1.
        bound : float
            Bound of the interval in which to sample for non compact
            ambient manifolds.
            Optional, default: 1.
        n_sampling_points : int
            Number of sampling points for the discrete curves.
            Optional, default : 10.

        Returns
        -------
        samples : array-like, shape=[..., n_sampling_points, {dim, [n, n]}]
            Points sampled on the hypersphere.
        """
        sample = self.ambient_manifold.random_point(
            n_samples * n_sampling_points)
        sample = gs.reshape(sample, (n_samples, n_sampling_points, -1))
        return sample[0] if n_samples == 1 else sample


class SRVMetric(RiemannianMetric):
    """Elastic metric defined using the Square Root Velocity Function.

    See [Sea2011]_ for details.

    Parameters
    ----------
    ambient_manifold : Manifold
        Manifold in which curves take values.
    metric : RiemannianMetric
        Metric to use on the ambient manifold. If None is passed, ambient
        manifold should have a metric attribute, which will be used.
        Optional, default : None.

    References
    ----------
    .. [Sea2011] A. Srivastava, E. Klassen, S. H. Joshi and I. H. Jermyn,
    "Shape Analysis of Elastic Curves in Euclidean Spaces,"
    in IEEE Transactions on Pattern Analysis and Machine Intelligence,
    vol. 33, no. 7, pp. 1415-1428, July 2011.
    """

    def __init__(self, ambient_manifold, metric=None):
        super(SRVMetric, self).__init__(dim=math.inf,
                                        signature=(math.inf, 0, 0))
        if metric is None:
            if hasattr(ambient_manifold, 'metric'):
                self.ambient_metric = ambient_manifold.metric
            else:
                raise ValueError('Instantiating an object of class '
                                 'DiscreteCurves requires either a metric'
                                 ' or an ambient manifold'
                                 ' equipped with a metric.')
        else:
            self.ambient_metric = metric
        self.l2_metric = lambda n: L2Metric(ambient_manifold, n_landmarks=n)

    def pointwise_inner_product(self, tangent_vec_a, tangent_vec_b,
                                base_curve):
        """Compute the pointwise inner product of pair of tangent vectors.

        Compute the point-wise inner-product between two tangent vectors
        at a base curve.

        Parameters
        ----------
        tangent_vec_a : array-like, shape=[..., n_sampling_points, ambient_dim]
            Tangent vector to discrete curve.
        tangent_vec_b : array-like, shape=[..., n_sampling_points, ambient_dim]
            Tangent vector to discrete curve.
        base_curve : array-like, shape=[..., n_sampling_points, ambient_dim]
            Point representing a discrete curve.

        Returns
        -------
        inner_prod : array-like, shape=[..., n_sampling_points]
            Point-wise inner-product.
        """
        def inner_prod_aux(vec_a, vec_b, curve):
            inner_prod = self.ambient_metric.inner_product(vec_a, vec_b, curve)
            return gs.squeeze(inner_prod)

        inner_prod = gs.vectorize(
            (tangent_vec_a, tangent_vec_b, base_curve),
            inner_prod_aux,
            dtype=gs.float32,
            multiple_args=True,
            signature='(i,j),(i,j),(i,j)->(i)')

        return inner_prod

    def pointwise_norm(self, tangent_vec, base_curve):
        """Compute the point-wise norm of a tangent vector at a base curve.

        Parameters
        ----------
        tangent_vec : array-like, shape=[..., n_sampling_points, ambient_dim]
            Tangent vector to discrete curve.
        base_curve : array-like, shape=[..., n_sampling_points, ambient_dim]
            Point representing a discrete curve.

        Returns
        -------
        norm : array-like, shape=[..., n_sampling_points]
            Point-wise norms.
        """
        sq_norm = self.pointwise_inner_product(
            tangent_vec_a=tangent_vec, tangent_vec_b=tangent_vec,
            base_curve=base_curve)
        return gs.sqrt(sq_norm)

    def square_root_velocity(self, curve):
        """Compute the square root velocity representation of a curve.

        The velocity is computed using the log map. In the case of several
        curves, an index selection procedure allows to get rid of the log
        between the end point of curve[k, :, :] and the starting point of
        curve[k + 1, :, :].

        Parameters
        ----------
        curve : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.

        Returns
        -------
        srv : array-like, shape=[..., n_sampling_points - 1, ambient_dim]
            Square-root velocity representation of a discrete curve.
        """
        curve = gs.to_ndarray(curve, to_ndim=3)
        n_curves, n_sampling_points, n_coords = curve.shape
        srv_shape = (n_curves, n_sampling_points - 1, n_coords)

        curve = gs.reshape(curve, (n_curves * n_sampling_points, n_coords))
        coef = gs.cast(gs.array(n_sampling_points - 1), gs.float32)
        velocity = coef * self.ambient_metric.log(point=curve[1:, :],
                                                  base_point=curve[:-1, :])
        velocity_norm = self.ambient_metric.norm(velocity, curve[:-1, :])
        srv = gs.einsum(
            '...i,...->...i', velocity, 1. / gs.sqrt(velocity_norm))

        index = gs.arange(n_curves * n_sampling_points - 1)
        mask = ~((index + 1) % n_sampling_points == 0)
        srv = gs.reshape(srv[mask], srv_shape)

        return srv

    def square_root_velocity_inverse(self, srv, starting_point):
        """Retrieve a curve from sqrt velocity rep and starting point.

        Parameters
        ----------
        srv : array-like, shape=[..., n_sampling_points - 1, ambient_dim]
            Square-root velocity representation of a discrete curve.
        starting_point : array-like, shape=[..., ambient_dim]
            Point of the ambient manifold to use as start of the retrieved
            curve.

        Returns
        -------
        curve : array-like, shape=[..., n_sampling_points, ambient_dim]
            Curve retrieved from its square-root velocity.
        """
        if not isinstance(self.ambient_metric, EuclideanMetric):
            raise AssertionError('The square root velocity inverse is only '
                                 'implemented for discrete curves embedded '
                                 'in a Euclidean space.')
        if gs.ndim(srv) != gs.ndim(starting_point):
            starting_point = gs.to_ndarray(
                starting_point, to_ndim=srv.ndim, axis=1)
        srv_shape = srv.shape
        srv = gs.to_ndarray(srv, to_ndim=3)
        n_curves, n_sampling_points_minus_one, n_coords = srv.shape

        srv = gs.reshape(srv,
                         (n_curves * n_sampling_points_minus_one, n_coords))
        srv_norm = self.ambient_metric.norm(srv)
        delta_points = gs.einsum(
            '...,...i->...i', 1 / n_sampling_points_minus_one * srv_norm, srv)
        delta_points = gs.reshape(delta_points, srv_shape)
        curve = gs.concatenate((starting_point, delta_points), -2)
        curve = gs.cumsum(curve, -2)

        return curve

    def d_square_root_velocity(self, tangent_vec, curve):
        """Compute differential of the square root velocity transform.
        """
        if not isinstance(self.ambient_metric, EuclideanMetric):
            raise AssertionError('The differential of the square root '
                                 'velocity function is only implemented for '
                                 'discrete curves embedded in a Euclidean '
                                 'space.')
        n_sampling_points = curve.shape[-2]
        d_vec = n_sampling_points * (tangent_vec[1:, :] - tangent_vec[:-1, :])
        velocity_vec = n_sampling_points * (curve[1:, :] - curve[:-1, :])
        velocity_norm = self.ambient_metric.norm(velocity_vec)
        unit_velocity_vec = gs.einsum(
            'ij,i->ij', velocity_vec, 1 / velocity_norm)
        d_vec_tangential = gs.einsum(
            'ij,i->ij', unit_velocity_vec,
            self.ambient_metric.inner_product(d_vec, unit_velocity_vec))
        d_srv_vec = d_vec - 1 / 2 * d_vec_tangential
        d_srv_vec = gs.einsum(
            'ij,i->ij', d_srv_vec, 1 / velocity_norm**(1 / 2))

        return d_srv_vec

    def inner_product(self, tangent_vec_a, tangent_vec_b, curve):
        """Compute inner product between two tangent vectors.

        The SRV metric is used, and is computed as pullback of the
        L2 metric by the square root velocity transform.
        """
        if not isinstance(self.ambient_metric, EuclideanMetric):
            raise AssertionError('The square root velocity inner product '
                                 'is only implemented for discrete curves '
                                 'embedded in a Euclidean space.')
        n_sampling_points = curve.shape[-2]
        d_srv_vec_a = self.d_square_root_velocity(tangent_vec_a, curve)
        d_srv_vec_b = self.d_square_root_velocity(tangent_vec_b, curve)
        inner_prod = self.l2_metric(n_sampling_points - 1).inner_product(
            d_srv_vec_a, d_srv_vec_b) / n_sampling_points

        return inner_prod

    def srv_inner_product(self, srv_1, srv_2):
        """
        Compute the L² inner_product between two srv representations.

        Parameters
        ----------
        srv_1 : array-like, shape=[..., n_sampling_points, ambient_dim]
            Srv representation.
        srv_2 : array-like, shape=[..., n_sampling_points, ambient_dim]
            Srv representation.

        Return
        ------
        inner_prod : array-like, shape=[...]
            L² inner product between the two srv representations.
        """
        n_sampling_points = srv_1.shape[-2]

        l2_inner_prod = self.l2_metric(n_sampling_points).inner_product
        inner_prod = l2_inner_prod(srv_1, srv_2) / (n_sampling_points)

        return inner_prod

    def srv_norm(self, srv):
        """
        Compute the L² norm of a srv representation of a curve.

        Parameters
        ----------
        srv : array-like, shape=[..., n_sampling_points, ambient_dim]
            Srv representation of a curve

        Return
        ------
        norm : array-like, shape=[...]
            L² norm of the srv representation.
        """
        squared_norm = self.srv_inner_product(srv, srv)
        norm = gs.sqrt(squared_norm)

        return norm

    def exp(self, tangent_vec, base_point):
        """Compute Riemannian exponential of tangent vector wrt to base curve.

        Parameters
        ----------
        tangent_vec : array-like, shape=[..., n_sampling_points, ambient_dim]
            Tangent vector to discrete curve.
        base_point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.

        Return
        ------
        end_curve :  array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve, result of the Riemannian exponential.
        """
        if not isinstance(self.ambient_metric, EuclideanMetric):
            raise AssertionError('The exponential map is only implemented '
                                 'for discrete curves embedded in a '
                                 'Euclidean space.')
        base_point = gs.to_ndarray(base_point, to_ndim=3)
        tangent_vec = gs.to_ndarray(tangent_vec, to_ndim=3)
        n_sampling_points = base_point.shape[1]

        base_curve_srv = self.square_root_velocity(base_point)

        tangent_vec_derivative = (n_sampling_points - 1) * (
            tangent_vec[:, 1:, :] - tangent_vec[:, :-1, :])
        base_curve_velocity = (n_sampling_points - 1) * (
            base_point[:, 1:, :] - base_point[:, :-1, :])
        base_curve_velocity_norm = self.pointwise_norm(
            base_curve_velocity, base_point[:, :-1, :])

        inner_prod = self.pointwise_inner_product(
            tangent_vec_derivative, base_curve_velocity, base_point[:, :-1, :])
        coef_1 = 1 / gs.sqrt(base_curve_velocity_norm)
        coef_2 = -1 / (2 * base_curve_velocity_norm**(5 / 2)) * inner_prod

        term_1 = gs.einsum('ij,ijk->ijk', coef_1, tangent_vec_derivative)
        term_2 = gs.einsum('ij,ijk->ijk', coef_2, base_curve_velocity)
        srv_initial_derivative = term_1 + term_2

        end_curve_srv = self.l2_metric(n_sampling_points - 1).exp(
            tangent_vec=srv_initial_derivative, base_point=base_curve_srv)
        end_curve_starting_point = self.ambient_metric.exp(
            tangent_vec=tangent_vec[:, 0, :], base_point=base_point[:, 0, :])
        end_curve = self.square_root_velocity_inverse(
            end_curve_srv, end_curve_starting_point)

        return end_curve

    def log(self, point, base_point):
        """Compute Riemannian logarithm of a curve wrt a base curve.

        Parameters
        ----------
        point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.
        base_point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve to use as base point.

        Returns
        -------
        log : array-like, shape=[..., n_sampling_points, ambient_dim]
            Tangent vector to a discrete curve.
        """
        if not isinstance(self.ambient_metric, EuclideanMetric):
            raise AssertionError('The logarithm map is only implemented '
                                 'for discrete curves embedded in a '
                                 'Euclidean space.')
        point = gs.to_ndarray(point, to_ndim=3)
        base_point = gs.to_ndarray(base_point, to_ndim=3)
        n_curves, n_sampling_points, n_coords = point.shape

        curve_srv = self.square_root_velocity(point)
        base_curve_srv = self.square_root_velocity(base_point)

        base_curve_velocity = (n_sampling_points - 1) * (base_point[:, 1:, :] -
                                                         base_point[:, :-1, :])
        base_curve_velocity_norm = self.pointwise_norm(base_curve_velocity,
                                                       base_point[:, :-1, :])

        inner_prod = self.pointwise_inner_product(curve_srv - base_curve_srv,
                                                  base_curve_velocity,
                                                  base_point[:, :-1, :])
        coef_1 = gs.sqrt(base_curve_velocity_norm)
        coef_2 = 1 / base_curve_velocity_norm**(3 / 2) * inner_prod

        term_1 = gs.einsum('ij,ijk->ijk', coef_1, curve_srv - base_curve_srv)
        term_2 = gs.einsum('ij,ijk->ijk', coef_2, base_curve_velocity)
        log_derivative = term_1 + term_2

        log_starting_points = self.ambient_metric.log(
            point=point[:, 0, :], base_point=base_point[:, 0, :])
        log_starting_points = gs.to_ndarray(
            log_starting_points, to_ndim=3, axis=1)

        log_cumsum = gs.hstack(
            [gs.zeros((n_curves, 1, n_coords)),
             gs.cumsum(log_derivative, -2)])
        log = log_starting_points + 1 / (n_sampling_points - 1) * log_cumsum

        return log

    def geodesic(self,
                 initial_curve,
                 end_curve=None,
                 initial_tangent_vec=None):
        """Compute geodesic from initial curve and end curve end curve.

        Geodesic specified either by an initial curve and an end curve,
        either by an initial curve and an initial tangent vector.

        Parameters
        ----------
        initial_curve : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.
        end_curve : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve. If None, an initial tangent vector must be given.
            Optional, default : None
        initial_tangent_vec : array-like,
            shape=[..., n_sampling_points, ambient_dim]
            Tangent vector at base curve, the initial speed of the geodesics.
            If None, an end curve must be given and a logarithm is computed.
            Optional, default : None

        Returns
        -------
        curve_on_geodesic : callable
            The time parameterized geodesic curve.
        """
        if not isinstance(self.ambient_metric, EuclideanMetric):
            raise AssertionError('The geodesics are only implemented for '
                                 'discrete curves embedded in a '
                                 'Euclidean space.')
        curve_ndim = 2
        initial_curve = gs.to_ndarray(initial_curve, to_ndim=curve_ndim + 1)

        if end_curve is None and initial_tangent_vec is None:
            raise ValueError('Specify an end curve or an initial tangent '
                             'vector to define the geodesic.')
        if end_curve is not None:
            end_curve = gs.to_ndarray(end_curve, to_ndim=curve_ndim + 1)
            shooting_tangent_vec = self.log(point=end_curve,
                                            base_point=initial_curve)
            if initial_tangent_vec is not None:
                if not gs.allclose(shooting_tangent_vec, initial_tangent_vec):
                    raise RuntimeError(
                        'The shooting tangent vector is too'
                        ' far from the initial tangent vector.')
            initial_tangent_vec = shooting_tangent_vec
        initial_tangent_vec = gs.array(initial_tangent_vec)
        initial_tangent_vec = gs.to_ndarray(initial_tangent_vec,
                                            to_ndim=curve_ndim + 1)

        def path(t):
            t = gs.cast(t, gs.float32)
            t = gs.to_ndarray(t, to_ndim=1)
            t = gs.to_ndarray(t, to_ndim=2, axis=1)
            new_initial_curve = gs.to_ndarray(initial_curve,
                                              to_ndim=curve_ndim + 1)
            new_initial_tangent_vec = gs.to_ndarray(initial_tangent_vec,
                                                    to_ndim=curve_ndim + 1)

            tangent_vecs = gs.einsum('il,nkm->ikm', t, new_initial_tangent_vec)

            curve_at_time_t = []
            for tan_vec in tangent_vecs:
                curve_at_time_t.append(
                    self.exp(tan_vec, new_initial_curve))
            return gs.stack(curve_at_time_t)

        return path

    def dist(self, point_a, point_b, **kwargs):
        """Geodesic distance between two curves.

        Parameters
        ----------
        point_a : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.
        point_b : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.

        Returns
        -------
        dist : array-like, shape=[...,]
        """
        if not isinstance(self.ambient_metric, EuclideanMetric):
            raise AssertionError('The distance is only implemented for '
                                 'discrete curves embedded in a '
                                 'Euclidean space.')
        if point_a.shape != point_b.shape:
            raise ValueError('The curves need to have the same shapes.')

        srv_a = self.square_root_velocity(point_a)
        srv_b = self.square_root_velocity(point_b)
        n_sampling_points = srv_a.shape[-2]
        dist_starting_points = self.ambient_metric.dist(
            point_a[0, :], point_b[0, :])
        dist_srvs = self.l2_metric(n_sampling_points).dist(srv_a, srv_b)
        dist = gs.sqrt(dist_starting_points**2 + dist_srvs**2)

        return dist

    # TODO (alebrigant): generalize from_vector_to_diagonal_matrix to k
    # diagonals and modify tensorflow vstack and hstack.
    def space_derivative(self, curve):
        """Compute space derivative of curve using centered differences.

        Parameters
        ----------
        curve : array-like, shape=[..., n_points, ambient_dim]
            Discrete curve.

        Returns
        -------
        space_deriv : array-like, shape=[...,n_points, ambient_dim]
        """
        n_points = curve.shape[-2]

        vec_1 = gs.squeeze(gs.hstack((
            gs.array([[-1.]]),
            gs.zeros((1, n_points - 2)),
            gs.array([[1.]]))))
        vec_2 = gs.squeeze(gs.hstack((
            1 / 2 * gs.ones((1, n_points - 2)),
            gs.array([[1.]]))))
        vec_3 = gs.squeeze(gs.hstack((
            gs.array([[1.]]),
            1 / 2 * gs.ones((1, n_points - 2)))))

        mat_1 = from_vector_to_diagonal_matrix(vec_1)
        mat_2 = from_vector_to_diagonal_matrix(vec_2)
        mat_3 = from_vector_to_diagonal_matrix(vec_3)

        mat_2 = gs.hstack((mat_2, gs.zeros((n_points - 1, 1))))
        mat_2 = gs.vstack((gs.zeros((1, n_points)), mat_2))
        mat_3 = gs.hstack((gs.zeros((n_points - 1, 1)), mat_3))
        mat_3 = gs.vstack((mat_3, gs.zeros((1, n_points))))
        mat_space_deriv = mat_1 - mat_2 + mat_3

        space_deriv = n_points * gs.matmul(mat_space_deriv, curve)

        return space_deriv


class ClosedDiscreteCurves(Manifold):
    r"""Space of closed discrete curves sampled at points in ambient_manifold.

    Each individual curve is represented by a 2d-array of shape `[
    n_sampling_points, ambient_dim]`.

    Parameters
    ----------
    ambient_manifold : Manifold
        Manifold in which curves take values.

    Attributes
    ----------
    ambient_manifold : Manifold
        Manifold in which curves take values.
    l2_metric : callable
        Function that takes as argument an integer number of sampled points
        and returns the corresponding L2 metric (product) metric,
        a RiemannianMetric object
    square_root_velocity_metric : RiemannianMetric
        Square root velocity metric.
    """

    def __init__(self, ambient_manifold):
        super(ClosedDiscreteCurves, self).__init__(dim=math.inf)
        self.ambient_manifold = ambient_manifold
        self.l2_metric = lambda n: L2Metric(
            self.ambient_manifold, n_landmarks=n)
        self.square_root_velocity_metric = ClosedSRVMetric(ambient_manifold)

    def belongs(self, point, atol=gs.atol):
        """Test whether a point belongs to the manifold.

        Test that all points of the curve belong to the ambient manifold.

        Parameters
        ----------
        point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Point representing a discrete curve.
        atol : float
            Absolute tolerance.
            Optional, default: backend atol.

        Returns
        -------
        belongs : bool
            Boolean evaluating if point belongs to the space of discrete
            curves.
        """
        raise NotImplementedError(
            'The belongs method is not implemented.'
        )

    def is_tangent(self, vector, base_point, atol=gs.atol):
        """Check whether the vector is tangent at a curve.

        A vector is tangent at a curve if it is a vector field along that
        curve.

        Parameters
        ----------
        vector : array-like, shape=[..., n_sampling_points, ambient_dim]
            Vector.
        base_point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.
        atol : float
            Absolute tolerance.
            Optional, default: backend atol.

        Returns
        -------
        is_tangent : bool
            Boolean denoting if vector is a tangent vector at the base point.
        """
        raise NotImplementedError(
            'The is_tangent method is not implemented.'
        )

    def to_tangent(self, vector, base_point):
        """Project a vector to a tangent space of the manifold.

        As tangent vectors are vector fields along a curve, each component of
        the vector is projected to the tangent space of the corresponding
        point of the discrete curve. The number of sampling points should
        match in the vector and the base_point.

        Parameters
        ----------
        vector : array-like, shape=[..., n_sampling_points, ambient_dim]
            Vector.
        base_point : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.

        Returns
        -------
        tangent_vec : array-like, shape=[..., n_sampling_points, ambient_dim]
            Tangent vector at base point.
        """
        raise NotImplementedError(
            'The to_tangent method is not implemented.'
        )

    def random_point(self, n_samples=1, bound=1., n_sampling_points=10):
        """Sample random curves.

        If the ambient manifold is compact, a uniform distribution is used.

        Parameters
        ----------
        n_samples : int
            Number of samples.
            Optional, default: 1.
        bound : float
            Bound of the interval in which to sample for non compact
            ambient manifolds.
            Optional, default: 1.
        n_sampling_points : int
            Number of sampling points for the discrete curves.
            Optional, default : 10.

        Returns
        -------
        samples : array-like, shape=[..., n_sampling_points, {dim, [n, n]}]
            Points sampled on the hypersphere.
        """
        raise NotImplementedError(
            'The random_point method is not implemented.'
        )

    def project(self, curve, atol=gs.atol, max_iter=1000):
        """Project a discrete curve into the space of closed discrete curves.

        Parameters
        ----------
        curve : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.
        atol : float
            Tolerance of the projection algorithm.
            Optional, default: backend atol.
        max_iter : float
            Maximum number of iteration of the algorithm.
            Optional, default: 1000

        Returns
        -------
        proj : array-like, shape=[..., n_sampling_points, ambient_dim]
        """
        is_euclidean = isinstance(self.ambient_manifold, Euclidean)
        is_planar = is_euclidean and self.ambient_manifold.dim == 2

        if not is_planar:
            raise AssertionError('The projection is only implemented '
                                 'for discrete curves embedded in a'
                                 '2D Euclidean space.')

        srv_metric = self.square_root_velocity_metric
        srv = srv_metric.square_root_velocity(curve)[0]
        srv_proj = srv_metric.project_srv(srv, atol=atol, max_iter=max_iter)
        proj = srv_metric.square_root_velocity_inverse(srv_proj,
                                                       gs.array([curve[0]]))

        return proj


class ClosedSRVMetric(SRVMetric):
    """Elastic metric on closed curves.

    See [Sea2011]_ for details.

    Parameters
    ----------
    ambient_manifold : Manifold
        Manifold in which curves take values.

    References
    ----------
    .. [Sea2011] A. Srivastava, E. Klassen, S. H. Joshi and I. H. Jermyn,
    "Shape Analysis of Elastic Curves in Euclidean Spaces,"
    in IEEE Transactions on Pattern Analysis and Machine Intelligence,
    vol. 33, no. 7, pp. 1415-1428, July 2011.
    """

    def __init__(self, ambient_manifold):
        super(ClosedSRVMetric, self).__init__(ambient_manifold)

    def project_srv(self, srv, atol=gs.atol, max_iter=1000):
        """Project a point in the srv space into the space of closed curves srv.

        The algorithm is from the paper cited above and modifies the srv
        iteratively so that G(srv) = (0, ..., 0) with the paper's notation.

        Remark: for now, the algorithm might not converge for some curves such
        as segments.

        Parameters
        ----------
        srv : array-like, shape=[..., n_sampling_points, ambient_dim]
            Discrete curve.
        atol : float
            Tolerance of the projection algorithm.
            Optional, default: backend atol.
        max_iter : float
            Maximum number of iteration of the algorithm.
            Optional, default: 1000

        Returns
        -------
        proj : array-like, shape=[..., n_sampling_points, ambient_dim]
        """
        is_euclidean = isinstance(self.ambient_metric, EuclideanMetric)
        is_planar = is_euclidean and self.ambient_metric.dim == 2

        if not is_planar:
            raise AssertionError('The projection is only implemented '
                                 'for discrete curves embedded in a'
                                 '2D Euclidean space.')

        dim = self.ambient_metric.dim
        srv_inner_prod = self.srv_inner_product
        srv_norm = self.srv_norm
        inner_prod = self.ambient_metric.inner_product

        def g_criterion(srv, srv_norms):
            return gs.sum(srv * srv_norms[:, None], axis=0)

        initial_norm = srv_norm(srv)
        proj = srv
        proj_norms = self.ambient_metric.norm(proj)
        residual = g_criterion(proj, proj_norms)
        criteria = self.ambient_metric.norm(residual)

        nb_iter = 0

        while criteria >= atol and nb_iter < max_iter:

            jacobian_vec = []
            for i in range(dim):
                for j in range(i, dim):
                    coef = 3 * inner_prod(proj[:, i], proj[:, j])
                    jacobian_vec.append(coef)
            jacobian_vec = gs.stack(jacobian_vec)
            g_jacobian = SymmetricMatrices.from_vector(jacobian_vec)

            proj_squared_norm = srv_norm(proj) ** 2
            g_jacobian += proj_squared_norm * gs.eye(dim)
            beta = gs.linalg.inv(g_jacobian) @ residual

            e_1, e_2 = gs.array([1, 0]), gs.array([0, 1])
            grad_1 = proj_norms[:, None] * e_1
            grad_1 = grad_1 + (proj[:, 0] / proj_norms)[:, None] * proj
            grad_2 = proj_norms[:, None] * e_2
            grad_2 = grad_2 + (proj[:, 1] / proj_norms)[:, None] * proj

            basis_vector_1 = grad_1 / srv_norm(grad_1)
            grad_2_component = srv_inner_prod(grad_2, basis_vector_1)
            grad_2_proj = grad_2_component * basis_vector_1
            basis_vector_2 = grad_2 - grad_2_proj
            basis_vector_2 = basis_vector_2 / srv_norm(basis_vector_2)
            basis = gs.array([basis_vector_1, basis_vector_2])

            proj -= gs.sum(beta[:, None, None] * basis, axis=0)
            proj = proj * initial_norm / srv_norm(proj)
            proj_norms = self.ambient_metric.norm(proj)
            residual = g_criterion(proj, proj_norms)
            criteria = self.ambient_metric.norm(residual)

            nb_iter += 1

        return proj


class QuotientSRVMetric(SRVMetric):
    """Metric on shape space induced by the SRV metric.

    The space of parameterized curves is the total space of a principal
    bundle where the group action is given by reparameterization and the
    base space is the shape space. This is the class for the quotient metric
    induced on the shape space by the SRV metric.

    Each tangent vector to the space of parameterized curves can be
    split into a vertical part (tangent to the fibers of the principal
    bundle) and a horizontal part (orthogonal to the vertical part with
    respect to the SRV metric). The geodesics for the quotient metric on the
    shape space are the projections of the horizontal geodesics in the total
    space of parameterized curves. They can be computed using an algorithm
    that iteratively finds the best correspondence between two fibers of the
    principal bundle, see Reference below.

    References
    ----------
    .. [LAB2017] A. Le Brigant, M. Arnaudon and F. Barbaresco,
    "Optimal matching between curves in a manifold,"
    in International Conference on Geometric Science of Information,
    pp. 57-65, Springer, Cham, 2017.
    """
    def __init__(self, ambient_manifold):
        super(QuotientSRVMetric, self).__init__(ambient_manifold)

    def split_horizontal_vertical(self, tangent_vec, curve):
        """Split tangent vector into horizontal and vertical parts.

        Parameters
        ----------
        tangent_vec : array-like, shape=[n_sampling_points, ambient_dim]
            tangent vector to decompose into horizontal and vertical parts.
        curve : array-like, shape=[n_sampling_points, ambient_dim]
            base point of tangent_vec in the manifold of curves.

        Returns
        -------
        tangent_vec_hor : array-like, shape=[n_sampling_points, ambient_dim]
            horizontal part of tangent_vec.
        tangent_vec_ver : array-like, shape=[n_sampling_points, ambient_dim]
            vertical part of tangent_vec.
        """
        ambient_dim = curve.shape[-1]
        a_param = 1
        b_param = 1 / 2
        quotient = a_param / b_param

        position = curve[1:-1, :]
        d_pos = (curve[2:, :] - curve[:-2, :]) / 2
        d_vec = (tangent_vec[2:, :] - tangent_vec[:-2, :]) / 2
        d2_pos = curve[2:, :] - 2 * curve[1:-1, :] + curve[:-2, :]
        d2_vec = tangent_vec[2:, :] - 2 * tangent_vec[1:-1, :] \
            + tangent_vec[:-2, :]

        vec_a = self.pointwise_norm(d_pos, position) ** 2 - 1 / 2 * \
            self.pointwise_inner_product(d2_pos, d_pos, position)
        vec_b = -2 * self.pointwise_norm(d_pos, position) ** 2 \
            - quotient**2 * (
            self.pointwise_norm(d2_pos, position) ** 2 -
            self.pointwise_inner_product(d2_pos, d_pos, position) ** 2 /
            self.pointwise_norm(d_pos, position) ** 2)
        vec_c = self.pointwise_norm(d_pos, position) ** 2 + 1 / 2 * \
            self.pointwise_inner_product(d2_pos, d_pos, position)
        vec_d = self.pointwise_norm(d_pos, position) * (
            self.pointwise_inner_product(d2_vec, d_pos, position) -
            (quotient**2 - 1) *
            self.pointwise_inner_product(d_vec, d2_pos, position) +
            (quotient**2 - 2) *
            self.pointwise_inner_product(d2_pos, d_pos, position) *
            self.pointwise_inner_product(d_vec, d_pos, position) /
            self.pointwise_norm(d_pos, position) ** 2)

        linear_system = np.diag(vec_a[:-1], 1) + np.diag(vec_b) + \
            np.diag(vec_c[1:], -1)
        vertical_norm = gs.to_ndarray(gs.from_numpy(
            np.linalg.solve(linear_system, vec_d)), to_ndim=2)
        vertical_norm = gs.squeeze(gs.hstack(
            (gs.array([[0.]]), vertical_norm, gs.array([[0.]]))))

        unit_speed = gs.einsum(
            'ij,i->ij', d_pos, 1 / self.pointwise_norm(d_pos, position))
        tangent_vec_ver = gs.vstack([
            gs.zeros((1, ambient_dim)),
            gs.einsum('ij,i->ij', unit_speed, vertical_norm[1:-1]),
            gs.zeros((1, ambient_dim))])
        tangent_vec_hor = tangent_vec - tangent_vec_ver

        return tangent_vec_hor, tangent_vec_ver, vertical_norm

    def horizontal_geodesic(self, initial_curve, end_curve, threshold=1e-3):
        """Compute horizontal geodesic between two curves.
        """
        n_points = initial_curve.shape[0]
        t_space = np.linspace(0., 1., n_points)
        spline_b = CubicSpline(t_space, end_curve, axis=0)

        def construct_reparametrization(n_times, vertical_norm,
                                        space_deriv_norm):
            rep = gs.zeros((n_times, n_points))
            rep_space_deriv = gs.zeros((n_times, n_points))
            rep_time_deriv = gs.zeros((n_times - 1, n_points))
            test_rep = gs.zeros(n_times)
            rep[0, :] = gs.linspace(0., 1., n_points)
            rep[:, -1] = gs.ones(n_times)
            for i in range(n_times - 1):
                rep_space_deriv[i, 0] = n_points * (rep[i, 1] - rep[i, 0])
                rep_time_deriv[i, 0] = rep_space_deriv[i, 0] * \
                    vertical_norm[i, 0] / space_deriv_norm[i, 0]
                rep[i + 1, 0] = rep[i, 0] + rep_time_deriv[i, 0] / n_times
                for j in range(1, n_points - 1):
                    d_rep_plus = rep[i, j + 1] - rep[i, j]
                    d_rep_minus = rep[i, j] - rep[i, j - 1]
                    if vertical_norm[i, j] > 0:
                        rep_space_deriv[i, j] = n_points * d_rep_plus
                    else:
                        rep_space_deriv[i, j] = n_points * d_rep_minus
                    rep_time_deriv[i, j] = rep_space_deriv[i, j] * \
                        vertical_norm[i, j] / space_deriv_norm[i, j]
                    rep[i + 1, j] = rep[i, j] + rep_time_deriv[i, j] / n_times

                test_rep[i] = gs.sum(rep[i + 1, 2:] - rep[i + 1, 1:-1] < 0)
                if np.any(test_rep):
                    print(test_rep)
                    print('Warning: phi(s) is non increasing for at least '
                          'one time s.')
            return rep

        def invert_reparametrization(repar, geod, repar_inverse_end,
                                     counter):
            n_times = repar.shape[0]
            initial_curve = geod[0]
            horizontal_path = gs.zeros(geod.shape)
            horizontal_path[0, :, :] = initial_curve
            for i in range(1, n_times - 1):
                spline_i = CubicSpline(t_space, geod[i, :, :], axis=0)
                repar_inverse = CubicSpline(repar[i, :], t_space)
                horizontal_path[i, :, :] = spline_i(repar_inverse(t_space))

            repar_inverse_end.append(CubicSpline(repar[-1, :], t_space))
            arg = t_space
            for i in range(counter + 1):
                arg = repar_inverse_end[- 1 - i](arg)
            horizontal_path[-1, :, :] = spline_b(arg)
            return horizontal_path

        def horizontal_path(t):
            n_times = len(t)
            current_end_curve = end_curve.copy()
            repar_inverse_end = []
            gap = 1.
            counter = 0

            while(gap > threshold):
                srv_geod_fun = self.geodesic(
                    initial_curve=initial_curve, end_curve=current_end_curve)
                geod = srv_geod_fun(t)

                time_deriv = n_times * (geod[1:] - geod[:-1])
                vertical_norm = gs.zeros((n_times - 1, n_points))
                for i in range(n_times - 1):
                    _, _, vertical_norm[i, :] = self.split_horizontal_vertical(
                        time_deriv[i], geod[i])

                space_deriv = self.space_derivative(geod)
                space_deriv_norm = self.ambient_metric.norm(space_deriv)

                repar = construct_reparametrization(
                    n_times, vertical_norm, space_deriv_norm)

                horizontal_path = invert_reparametrization(
                    repar, geod, repar_inverse_end, counter)

                new_end_curve = horizontal_path[-1, :, :]
                gap = (gs.sum(gs.linalg.norm(
                    new_end_curve - current_end_curve, axis=-1)**2))**(1 / 2)
                current_end_curve = new_end_curve.copy()
                print('gap is:', gap, 'min-mean-max vertical norm are',
                      np.around(np.min(vertical_norm), 3),
                      np.around(np.mean(vertical_norm), 3),
                      np.around(np.max(vertical_norm), 3))

                counter += 1
            return horizontal_path

        return horizontal_path
