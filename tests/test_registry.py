import pytest

from flowlab.models.registry import available, create


def test_all_models_registered():
    names = available()
    assert {"mlp", "iforest", "autoencoder"} <= set(names)


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        create("nope")
