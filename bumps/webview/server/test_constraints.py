"""
Tests for the constraints editor API endpoints (issue #391).
"""

import asyncio

import numpy as np

from bumps.curve import Curve
from bumps.fitproblem import FitProblem
from bumps.webview.server import api
from bumps.webview.server.state_hdf5_backed import ProblemState


def _line(x, a, b):
    return a * x + b


def _make_problem():
    """Two-model problem with four independent fitted parameters."""
    x = np.linspace(0, 1, 10)
    y = 2 * x + 1
    dy = np.full_like(x, 0.1)
    m1 = Curve(_line, x, y, dy, name="m1", a=2.0, b=1.0)
    m2 = Curve(_line, x, y, dy, name="m2", a=2.0, b=1.0)
    for m in (m1, m2):
        m.pars["a"].range(0, 5)
        m.pars["b"].range(0, 5)
    problem = FitProblem([m1, m2])
    return m1, m2, problem


def _install(problem):
    problem_state = ProblemState()
    problem_state.fitProblem = problem
    api.state.problem = problem_state


def _run(coro):
    return asyncio.run(coro)


def test_link_and_unlink():
    m1, m2, problem = _make_problem()
    _install(problem)
    b1, b2 = m1.pars["b"], m2.pars["b"]
    assert len(problem._parameters) == 4

    # Equality constraint: m2.b follows m1.b
    result = _run(api.link_parameters([b2.id], b1.id))
    assert result == {"linked": 1, "errors": []}
    assert b2.slot is b1
    assert len(problem._parameters) == 3  # b2 no longer fitted
    b1.value = 3.25
    assert float(b2.value) == 3.25

    # Self-link and circular links are rejected
    result = _run(api.link_parameters([b1.id], b1.id))
    assert result["linked"] == 0 and "itself" in result["errors"][0]
    result = _run(api.link_parameters([b1.id], b2.id))
    assert result["linked"] == 0 and "circular" in result["errors"][0]

    # Uncouple: b2 becomes independent at the current value
    result = _run(api.unlink_parameters([b2.id]))
    assert result == {"unlinked": 1, "errors": []}
    assert len(problem._parameters) == 4
    b1.value = 1.0
    assert float(b2.value) == 3.25  # no longer follows

    # Unlinking an unlinked parameter reports rather than failing
    result = _run(api.unlink_parameters([b2.id]))
    assert result["unlinked"] == 0 and "not linked" in result["errors"][0]


def test_merge_and_uncouple():
    m1, m2, problem = _make_problem()
    _install(problem)
    a1, a2 = m1.pars["a"], m2.pars["a"]

    # Identity constraint: every reference to a2 becomes a reference to a1
    result = _run(api.merge_parameters(a1.id, [a2.id]))
    assert result["merged"] == 1
    assert result["errors"] == [] and result["still_referenced"] == []
    assert m2.pars["a"] is a1
    assert len(problem._parameters) == 3

    # The shared parameter is reported with one site per model
    sites = _run(api.get_parameter_sites(a1.id))
    assert isinstance(sites, list)
    paths = [s["path"] for s in sites]
    assert len(paths) == 2 and all(".pars['a']" in p for p in paths), paths

    # Uncoupling splits the second occurrence into an independent copy
    result = _run(api.uncouple_parameter(a1.id))
    assert result["uncoupled"] == 1 and len(result["new_ids"]) == 1
    assert m1.pars["a"] is not m2.pars["a"]
    assert len(problem._parameters) == 4
    m1.pars["a"].value = 4.0
    assert float(m2.pars["a"].value) == 2.0  # independent again
    # The copy kept the name, value and bounds but got a new id
    copy_par = m2.pars["a"]
    assert copy_par.id in result["new_ids"]
    assert str(copy_par.name) == str(m1.pars["a"].name)

    # Uncoupling an unshared parameter reports an error
    result = _run(api.uncouple_parameter(a1.id))
    assert "nothing to uncouple" in result["error"]


def test_inequality_constraints():
    m1, m2, problem = _make_problem()
    _install(problem)
    a1, b1 = m1.pars["a"], m1.pars["b"]
    assert list(problem.constraints) == []

    # Parameter vs number (a=2 < 10: satisfied)
    result = _run(api.add_constraint(a1.id, "<", right_value=10.0))
    assert result["satisfied"] is True
    assert len(problem.constraints) == 1

    # Parameter vs parameter (a=2 > b=1: satisfied)
    result = _run(api.add_constraint(a1.id, ">", right_id=b1.id))
    assert result["satisfied"] is True
    assert len(problem.constraints) == 2

    # Bad inputs are rejected without changing the model
    assert "unknown operator" in _run(api.add_constraint(a1.id, "==", right_value=1.0))["error"]
    assert "itself" in _run(api.add_constraint(a1.id, "<", right_id=a1.id))["error"]
    assert "either right_id or right_value" in _run(api.add_constraint(a1.id, "<"))["error"]
    assert len(problem.constraints) == 2

    # Listed in get_constraints_info with index, text and satisfied flag
    info = _run(api.get_constraints_info())
    assert [c["index"] for c in info["inequalities"]] == [0, 1]
    assert all(c["satisfied"] for c in info["inequalities"])

    # Remove the first; the second shifts down
    result = _run(api.remove_constraint(0))
    assert "removed" in result
    assert len(problem.constraints) == 1
    assert "no constraint at index" in _run(api.remove_constraint(5))["error"]


def test_constraints_info_sections():
    m1, m2, problem = _make_problem()
    _install(problem)
    info = _run(api.get_constraints_info())
    assert info == {"inequalities": [], "links": [], "identities": []}

    _run(api.link_parameters([m2.pars["b"].id], m1.pars["b"].id))
    _run(api.merge_parameters(m1.pars["a"].id, [m2.pars["a"].id]))
    info = _run(api.get_constraints_info())

    assert len(info["links"]) == 1
    assert info["links"][0]["id"] == m2.pars["b"].id
    assert info["links"][0]["slot_repr"]  # shows the linked parameter

    assert len(info["identities"]) == 1
    identity = info["identities"][0]
    assert identity["id"] == m1.pars["a"].id
    assert len(identity["paths"]) == 2
