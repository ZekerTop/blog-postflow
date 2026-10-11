from app.adapters.base import split_blocks
from tests.conftest import BODY


def test_split_blocks_keeps_code_fence():
    assert len(split_blocks(BODY)) == 4

