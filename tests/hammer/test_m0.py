"""M0: dec-g1 through hammer.body (arcbatch) reproduces r08's curve sha."""

from arcagi.grow import curve as gc
from arcagi.hammer import body, epoch


def test_dec_g1_sha(tmp_path):
    if not body.ARCBATCH.exists():
        import pytest
        pytest.skip("native/bin/arcbatch not built")
    epoch.run_compat(tmp_path / "out", tmp_path / "lib", "native", threads=4,
                     log=lambda *_: None)
    assert gc.curve_sha(tmp_path / "out" / "curve.csv")[:12] == "7aebb3c73f28"
