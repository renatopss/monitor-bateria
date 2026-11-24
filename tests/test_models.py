import pytest

from monitor_bateria.models import Reading, Status


def test_ok_reading_valid():
    assert Reading("a", "A", Status.OK, 66).short() == "A: 66%"


@pytest.mark.parametrize("bad", [None, -1, 101, 50.5, True, "66"])
def test_ok_requires_valid_percent(bad):
    with pytest.raises(ValueError):
        Reading("a", "A", Status.OK, bad)


def test_non_ok_cannot_carry_percent():
    with pytest.raises(ValueError):
        Reading("a", "A", Status.ERROR, 50)


@pytest.mark.parametrize("status", [s for s in Status if s is not Status.OK])
def test_every_status_has_a_label(status):
    assert Reading("a", "A", status).short().startswith("A: ")
