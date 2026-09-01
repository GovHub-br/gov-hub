import pytest

# conftest.py wires up sys.path; import helpers directly.
import batching


class TestChunked:
    def test_splits_into_blocks(self) -> None:
        assert batching.chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_exact_multiple(self) -> None:
        assert batching.chunked([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_size_larger_than_list(self) -> None:
        assert batching.chunked([1, 2], 10) == [[1, 2]]

    def test_empty_list(self) -> None:
        assert batching.chunked([], 5) == []

    def test_preserves_order(self) -> None:
        flat = [x for block in batching.chunked(list(range(100)), 7) for x in block]
        assert flat == list(range(100))

    def test_covers_every_element_once(self) -> None:
        blocks = batching.chunked(list(range(10_000)), 50)
        assert len(blocks) == 200
        assert sum(len(b) for b in blocks) == 10_000

    def test_invalid_size(self) -> None:
        with pytest.raises(ValueError):
            batching.chunked([1, 2, 3], 0)


class TestPageStarts:
    def test_basic(self) -> None:
        assert batching.page_starts(40, 15) == [1, 16, 31]

    def test_matches_legacy_idiom(self) -> None:
        # The idiom this replaces across the page-based DAGs.
        for total in (0, 1, 7, 15, 16, 500):
            assert batching.page_starts(total, 15) == list(range(1, total + 1, 15))

    def test_custom_start(self) -> None:
        assert batching.page_starts(4, 2, start=0) == [0, 2]

    def test_invalid_block(self) -> None:
        with pytest.raises(ValueError):
            batching.page_starts(10, 0)


class TestBlockOffsets:
    def test_basic(self) -> None:
        assert batching.block_offsets(400, 150) == [0, 150, 300]

    def test_matches_legacy_idiom(self) -> None:
        for total in (0, 1, 150, 151, 300):
            assert batching.block_offsets(total, 150) == list(range(0, total, 150))


class TestLimitLocal:
    def test_no_env_returns_untouched(self, monkeypatch) -> None:
        monkeypatch.delenv("INGEST_MAX_ORGAOS", raising=False)
        items = list(range(50))
        assert batching.limit_local(items, "INGEST_MAX_ORGAOS") == items

    def test_truncates_when_set(self, monkeypatch) -> None:
        monkeypatch.setenv("INGEST_MAX_ORGAOS", "10")
        assert batching.limit_local(list(range(50)), "INGEST_MAX_ORGAOS") == list(
            range(10)
        )

    def test_no_truncation_when_below_cap(self, monkeypatch) -> None:
        monkeypatch.setenv("INGEST_MAX_ORGAOS", "10")
        assert batching.limit_local([1, 2, 3], "INGEST_MAX_ORGAOS") == [1, 2, 3]

    def test_non_integer_is_ignored(self, monkeypatch) -> None:
        monkeypatch.setenv("INGEST_MAX_ORGAOS", "abc")
        items = list(range(50))
        assert batching.limit_local(items, "INGEST_MAX_ORGAOS") == items

    def test_negative_is_ignored(self, monkeypatch) -> None:
        monkeypatch.setenv("INGEST_MAX_ORGAOS", "-5")
        items = list(range(50))
        assert batching.limit_local(items, "INGEST_MAX_ORGAOS") == items
