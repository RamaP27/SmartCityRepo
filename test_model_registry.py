"""
Unit tests for ModelRegistry — file-system operations tested via tmp_path fixture.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from shems.ml.model_registry import ModelRegistry

# ── Helpers ───────────────────────────────────────────────────────────────────


class _SimpleModel:
    """Minimal picklable object used in place of a real sklearn/torch model."""
    def __init__(self, value: float = 42.0):
        self.value = value

    def predict(self, X):
        return [self.value] * len(X)


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Point MODELS_DIR to a fresh tmp directory for each test and clear cache."""
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))
    # Patch the module-level MODELS_DIR and _cache
    import shems.ml.model_registry as reg_module
    monkeypatch.setattr(reg_module, "MODELS_DIR", tmp_path)
    reg_module._cache.clear()
    yield tmp_path
    reg_module._cache.clear()


# ── save ──────────────────────────────────────────────────────────────────────

def test_save_creates_joblib_file(isolated_registry):
    model = _SimpleModel(1.0)
    path = ModelRegistry.save("anomaly", "cluster_A", model)

    assert Path(path).exists()
    assert path.endswith(".joblib")


def test_save_writes_registry_json(isolated_registry):
    ModelRegistry.save("anomaly", "cluster_B", _SimpleModel())

    idx_path = isolated_registry / "registry.json"
    assert idx_path.exists()
    index = json.loads(idx_path.read_text())
    assert "anomaly/cluster_B" in index


def test_save_stores_metadata(isolated_registry):
    ModelRegistry.save("forecast", "zone1_1h", _SimpleModel(), metadata={"mae": 12.5})

    idx_path = isolated_registry / "registry.json"
    index = json.loads(idx_path.read_text())
    assert index["forecast/zone1_1h"]["metadata"]["mae"] == 12.5


def test_save_populates_in_memory_cache(isolated_registry):
    import shems.ml.model_registry as reg_module
    ModelRegistry.save("anomaly", "cluster_C", _SimpleModel(7.0))
    assert "anomaly/cluster_C" in reg_module._cache


def test_save_returns_path_string(isolated_registry):
    result = ModelRegistry.save("anomaly", "cluster_D", _SimpleModel())
    assert isinstance(result, str)


# ── load ──────────────────────────────────────────────────────────────────────

def test_load_returns_saved_model(isolated_registry):
    original = _SimpleModel(99.0)
    ModelRegistry.save("anomaly", "cluster_E", original)

    import shems.ml.model_registry as reg_module
    reg_module._cache.clear()  # Force disk read

    loaded = ModelRegistry.load("anomaly", "cluster_E")
    assert loaded is not None
    assert loaded.value == 99.0


def test_load_missing_model_returns_none(isolated_registry):
    result = ModelRegistry.load("anomaly", "nonexistent_key")
    assert result is None


def test_load_returns_from_cache_without_disk_read(isolated_registry, monkeypatch):
    import shems.ml.model_registry as reg_module
    sentinel = _SimpleModel(55.0)
    reg_module._cache["forecast/zone_X_6h"] = sentinel

    # If disk were hit, joblib.load would fail (file doesn't exist)
    result = ModelRegistry.load("forecast", "zone_X_6h")
    assert result is sentinel


def test_load_after_save_uses_cache(isolated_registry):
    import shems.ml.model_registry as reg_module
    model = _SimpleModel(3.14)
    ModelRegistry.save("anomaly", "cached_key", model)

    loaded = ModelRegistry.load("anomaly", "cached_key")
    # Should come from cache — same object identity
    assert loaded is reg_module._cache["anomaly/cached_key"]


# ── exists ────────────────────────────────────────────────────────────────────

def test_exists_true_after_save(isolated_registry):
    ModelRegistry.save("forecast", "zone_z_24h", _SimpleModel())
    assert ModelRegistry.exists("forecast", "zone_z_24h") is True


def test_exists_false_before_save(isolated_registry):
    assert ModelRegistry.exists("forecast", "ghost_model") is False


def test_exists_true_when_in_cache_only(isolated_registry):
    import shems.ml.model_registry as reg_module
    reg_module._cache["anomaly/cache_only"] = _SimpleModel()
    assert ModelRegistry.exists("anomaly", "cache_only") is True


# ── list_models ───────────────────────────────────────────────────────────────

def test_list_models_returns_only_matching_type(isolated_registry):
    ModelRegistry.save("anomaly", "hh_1", _SimpleModel())
    ModelRegistry.save("anomaly", "hh_2", _SimpleModel())
    ModelRegistry.save("forecast", "zone_1h", _SimpleModel())

    anomaly_models = ModelRegistry.list_models("anomaly")
    assert len(anomaly_models) == 2
    assert all(m["type"] == "anomaly" for m in anomaly_models)


def test_list_models_empty_for_unknown_type(isolated_registry):
    result = ModelRegistry.list_models("sustainability")
    assert result == []


def test_list_models_entry_has_required_keys(isolated_registry):
    ModelRegistry.save("anomaly", "hh_3", _SimpleModel(), metadata={"version": 1})
    entries = ModelRegistry.list_models("anomaly")

    entry = entries[0]
    assert "type" in entry
    assert "key" in entry
    assert "path" in entry
    assert "saved_at" in entry
    assert "metadata" in entry


# ── evict_cache ───────────────────────────────────────────────────────────────

def test_evict_cache_clears_all_entries(isolated_registry):
    import shems.ml.model_registry as reg_module
    ModelRegistry.save("anomaly", "hh_4", _SimpleModel())
    ModelRegistry.save("forecast", "zone_6h", _SimpleModel())

    assert len(reg_module._cache) >= 2
    ModelRegistry.evict_cache()
    assert len(reg_module._cache) == 0


# ── overwrite behaviour ───────────────────────────────────────────────────────

def test_save_overwrites_existing_model(isolated_registry):
    ModelRegistry.save("anomaly", "overwrite_key", _SimpleModel(1.0))
    ModelRegistry.save("anomaly", "overwrite_key", _SimpleModel(2.0))

    import shems.ml.model_registry as reg_module
    reg_module._cache.clear()

    loaded = ModelRegistry.load("anomaly", "overwrite_key")
    assert loaded.value == 2.0


def test_registry_json_updated_on_overwrite(isolated_registry):
    ModelRegistry.save("anomaly", "ow_key", _SimpleModel(), metadata={"v": 1})
    ModelRegistry.save("anomaly", "ow_key", _SimpleModel(), metadata={"v": 2})

    idx = json.loads((isolated_registry / "registry.json").read_text())
    assert idx["anomaly/ow_key"]["metadata"]["v"] == 2
