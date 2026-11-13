import pytest

from app.rag.knowledge_base import split_markdown
from app.rag.text import normalize, tokenize


@pytest.mark.parametrize(
    ("query", "expected_section"),
    [
        ("Tem opção sem glúten?", "Opções sem glúten"),
        ("Qual a taxa de entrega?", "Área e taxa de entrega"),
        ("Aceitam pix?", "Formas de pagamento"),
        ("Vocês abrem segunda?", "Horário de funcionamento"),
        ("Tem prato vegano?", "Pratos veganos e vegetarianos"),
        ("Quanto tempo demora a entrega?", "Tempo de entrega"),
        ("Qual o pedido mínimo?", "Pedido mínimo"),
        ("Tem cerveja?", "Bebidas"),
    ],
)
def test_retrieves_expected_section(retriever, query, expected_section):
    results = retriever.search(query, top_k=3)
    assert results, f"nenhum resultado para {query!r}"
    assert results[0].chunk.section == expected_section


def test_results_are_sorted_by_score(retriever):
    results = retriever.search("pizza margherita preço", top_k=3)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0 < s <= 1.0001 for s in scores)


@pytest.mark.parametrize("query", ["Quem ganhou a Copa de 1970?", "qual a capital da frança"])
def test_out_of_scope_queries_score_below_threshold(retriever, settings, query):
    results = retriever.search(query)
    assert not results or results[0].score < settings.min_retrieval_score


def test_single_word_match_is_rejected_by_coverage(toolbox):
    # Regressão encontrada pela avaliação: "tempo" casava com "Tempo de entrega".
    result = toolbox.search_knowledge_base("Qual a previsão do tempo para amanhã em Paris?")
    assert result["found"] is False


def test_normalize_removes_accents_and_case():
    assert normalize("Glúten AÇÚCAR") == "gluten acucar"


def test_tokenize_drops_stopwords_and_expands_synonyms():
    assert "voce" not in tokenize("Você aceita pix?")
    assert "pagamento" in tokenize("aceita pix?", expand=True)


def test_split_markdown_creates_one_chunk_per_section():
    chunks = split_markdown("x.md", "# Doc\n\n## A\ntexto a\n\n## B\ntexto b\n")
    assert [c.section for c in chunks] == ["A", "B"]
    assert chunks[0].document == "Doc"
    assert chunks[1].ref == "x.md › B"


def test_split_markdown_joins_wrapped_lines_but_keeps_lists():
    chunks = split_markdown("x.md", "## A\nlinha um\ncontinua\n- item 1\n- item 2\n")
    assert chunks[0].text == "linha um continua\n- item 1\n- item 2"
