from app.rag import _build_context, _sanitize_chart


class TestSanitizeChart:
    def test_trims_trailing_zeros(self):
        cfg = {
            "type": "line",
            "title": "CPI",
            "labels": ["2020", "2021", "2022", "2023"],
            "datasets": [{"label": "inflacja", "data": [2.5, 3.1, 5.4, 0]}],
        }
        result = _sanitize_chart(cfg)
        assert result["labels"] == ["2020", "2021", "2022"]
        assert result["datasets"][0]["data"] == [2.5, 3.1, 5.4]

    def test_trims_trailing_nulls(self):
        cfg = {
            "type": "line",
            "title": "PKB",
            "labels": ["Q1", "Q2", "Q3", "Q4"],
            "datasets": [{"label": "wzrost", "data": [1.2, 2.3, None, None]}],
        }
        result = _sanitize_chart(cfg)
        assert result["labels"] == ["Q1", "Q2"]

    def test_all_zeros_returns_none(self):
        cfg = {
            "type": "bar",
            "title": "test",
            "labels": ["2020"],
            "datasets": [{"label": "x", "data": [0]}],
        }
        assert _sanitize_chart(cfg) is None

    def test_non_dict_returns_none(self):
        assert _sanitize_chart("not a dict") is None
        assert _sanitize_chart(None) is None
        assert _sanitize_chart([1, 2, 3]) is None

    def test_multiple_datasets_keeps_last_real_across_all(self):
        cfg = {
            "type": "line",
            "title": "porównanie",
            "labels": ["2021", "2022", "2023"],
            "datasets": [
                {"label": "A", "data": [1.0, 2.0, 0]},
                {"label": "B", "data": [3.0, 0, 0]},
            ],
        }
        result = _sanitize_chart(cfg)
        # dataset A has real value at index 1 (2.0), so trim to index 1
        assert result["labels"] == ["2021", "2022"]

    def test_no_datasets_returns_cfg_unchanged(self):
        cfg = {"type": "line", "title": "t", "labels": [], "datasets": []}
        result = _sanitize_chart(cfg)
        assert result == cfg


class TestBuildContext:
    def test_formats_source_label(self):
        chunks = [
            {
                "text": "PKB wzrósł o 2.1%",
                "metadata": {"source": "GUS", "date": "2024-Q1", "title": "PKB", "url": "https://gus.pl"},
            }
        ]
        context, _sources = _build_context(chunks)
        assert "GUS" in context
        assert "2024-Q1" in context
        assert "PKB wzrósł" in context

    def test_returns_correct_sources_shape(self):
        chunks = [
            {"text": "chunk", "metadata": {"source": "NBP", "date": "2024", "title": "Raport", "url": "https://nbp.pl"}},
        ]
        _, sources = _build_context(chunks)
        assert len(sources) == 1
        assert sources[0] == {"title": "Raport", "source": "NBP", "date": "2024", "url": "https://nbp.pl"}

    def test_multiple_chunks_separated_by_divider(self):
        chunks = [
            {"text": "chunk1", "metadata": {"source": "NBP", "date": "", "title": "", "url": ""}},
            {"text": "chunk2", "metadata": {"source": "GUS", "date": "", "title": "", "url": ""}},
        ]
        context, sources = _build_context(chunks)
        assert len(sources) == 2
        assert "---" in context
        assert "chunk1" in context
        assert "chunk2" in context

    def test_missing_metadata_fields_default_empty(self):
        chunks = [{"text": "dane", "metadata": {}}]
        context, sources = _build_context(chunks)
        # sources dict uses "" default; "Nieznane" appears only in the context label
        assert sources[0]["source"] == ""
        assert sources[0]["title"] == ""
        assert "Nieznane" in context
