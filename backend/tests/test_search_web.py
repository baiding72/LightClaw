from app.tools.search_web import deduplicate_search_results, normalize_search_result_url


def test_normalize_search_result_url_extracts_duckduckgo_redirect_target() -> None:
    raw_url = (
        "https://duckduckgo.com/l/?uddg="
        "https%3A%2F%2Fopenai.com%2Fgpt-5%2F%3Futm_source%3Dnewsletter"
    )

    assert normalize_search_result_url(raw_url) == "https://openai.com/gpt-5/"


def test_deduplicate_search_results_skips_tracking_and_duplicate_urls() -> None:
    results = [
        {
            "title": "Ad",
            "url": "https://duckduckgo.com/y.js?foo=bar",
            "snippet": "tracked",
            "source": "duckduckgo",
        },
        {
            "title": "GPT‑5 is here - OpenAI",
            "url": "https://openai.com/gpt-5/?utm_source=duckduckgo",
            "snippet": "first",
            "source": "duckduckgo",
        },
        {
            "title": "GPT‑5 is here - OpenAI duplicate",
            "url": "https://openai.com/gpt-5/",
            "snippet": "second",
            "source": "duckduckgo",
        },
    ]

    deduplicated = deduplicate_search_results(results, limit=5)

    assert len(deduplicated) == 1
    assert deduplicated[0]["url"] == "https://openai.com/gpt-5/"
