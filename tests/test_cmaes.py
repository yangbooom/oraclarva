import pytest

np = pytest.importorskip("numpy")

from oraclarva.cmaes import CMAES


def _run(f, x0, sigma, gens):
    es = CMAES(mean=np.array(x0, float), sigma=sigma, seed=1)
    for _ in range(gens):
        xs = es.ask()
        es.tell(xs, np.array([f(x) for x in xs]))
    return es


def test_cmaes_solves_shifted_sphere():
    target = np.array([1.0, -2.0, 0.5, 3.0])
    es = _run(lambda x: float(np.sum((x - target) ** 2)), np.zeros(4), 1.0, 120)
    assert es.best_f < 1e-6
    assert np.allclose(es.best_x, target, atol=1e-3)


def test_cmaes_handles_ill_conditioned_ellipsoid():
    scales = np.array([1.0, 10.0, 100.0])
    es = _run(lambda x: float(np.sum((scales * x) ** 2)), np.ones(3), 0.5, 200)
    assert es.best_f < 1e-6
