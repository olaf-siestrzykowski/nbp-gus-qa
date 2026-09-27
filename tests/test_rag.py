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


class TestStreamAnswerErrors:
    def test_llm_failure_yields_error_event_after_sources(self):
        from unittest.mock import MagicMock, patch

        from app import rag

        chunk = {
            "text": "CPI 2022: 114.4",
            "metadata": {"title": "GUS CPI", "source": "GUS", "date": "2022", "url": ""},
        }
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("model_decommissioned")
        with patch("app.rag.query", return_value=[chunk]), patch("app.rag._get_client", return_value=client):
            events = list(rag.stream_answer("inflacja 2022?"))

        assert [e[0] for e in events] == ["sources", "error"]
        assert events[-1][1] == rag.LLM_ERROR_MESSAGE


class TestRouting:
    def test_indicator_questions_are_routed(self):
        from app.rag import _route

        assert _route("Jaka była inflacja CPI w 2022?") == ["GUS BDL - CPI"]
        assert _route("Ile wynosiła stopa bezrobocia w 2013 roku?") == ["GUS BDL - Bezrobocie"]
        assert _route("Przeciętne wynagrodzenie brutto w 2024") == ["GUS BDL - Wynagrodzenia"]
        assert "GUS BDL - CPI kategorie" in _route("Jak zmieniły się ceny żywności w 2023?")
        assert _route("Ile kosztuje gram złota?") == ["NBP API - Ceny złota"]

    def test_currency_and_statements_are_not_routed(self):
        from app.rag import _route

        assert _route("Ile kosztuje 100 złotych w euro?") == []
        assert _route("Kiedy RPP podniosła stopy procentowe?") == []

    def test_routed_tables_come_first_without_duplicates(self):
        from unittest.mock import patch

        from app import rag

        table = {"text": "CPI table", "metadata": {"source": "GUS BDL - CPI"}, "distance": 0.0}
        other = {"text": "RPP statement", "metadata": {"source": "NBP - RPP"}, "distance": 0.3}
        with patch("app.rag.get_by_source", return_value=[table]), \
             patch("app.rag.query", return_value=[other, dict(table, distance=0.2)]):
            chunks = rag.retrieve("inflacja w 2022")
        assert [c["text"] for c in chunks] == ["CPI table", "RPP statement"]


class TestModelFallback:
    @staticmethod
    def _rate_limit(message):
        from unittest.mock import MagicMock

        from groq import RateLimitError

        return RateLimitError(message, response=MagicMock(status_code=429), body=None)

    def test_daily_quota_falls_back_to_second_model(self):
        from unittest.mock import MagicMock, patch

        from app import rag

        client = MagicMock()
        client.chat.completions.create.side_effect = [
            self._rate_limit("Rate limit reached on tokens per day (TPD)"), "ok",
        ]
        with patch("app.rag._get_client", return_value=client):
            assert rag._complete("openai/gpt-oss-120b", messages=[]) == "ok"
        models = [c.kwargs["model"] for c in client.chat.completions.create.call_args_list]
        assert models == ["openai/gpt-oss-120b", rag.settings.groq_fallback_model]

    def test_short_burst_limit_is_not_hidden(self):
        from unittest.mock import MagicMock, patch

        import pytest

        from app import rag

        client = MagicMock()
        client.chat.completions.create.side_effect = self._rate_limit("tokens per minute (TPM)")
        with patch("app.rag._get_client", return_value=client), pytest.raises(Exception):
            rag._complete("openai/gpt-oss-120b", messages=[])
        assert client.chat.completions.create.call_count == 1


class TestEmbeddingRetries:
    def test_rate_limited_embedding_request_is_retried(self):
        from unittest.mock import MagicMock, patch

        from app import vectorstore

        limited = MagicMock(status_code=429, headers={"Retry-After": "1"})
        ok = MagicMock(status_code=200, headers={})
        ok.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}
        with patch.object(vectorstore.requests, "post", side_effect=[limited, ok]) as post, \
             patch.object(vectorstore.time, "sleep") as sleep:
            assert vectorstore._embed(["tekst"], task="retrieval.query") == [[0.1, 0.2]]
        assert post.call_count == 2
        sleep.assert_called_once_with(1.0)
