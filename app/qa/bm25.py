from rank_bm25 import BM25Okapi

from app.qa.text import tokens


def bm25_rank(documents: list[str], query: str) -> list[int]:
    """Indexes of the documents that share a word with the query, best first.

    A document that shares no word with the question is never returned, so a question the papers
    do not cover comes back empty and the answer is "that is not in your papers".
    """
    query_tokens = tokens(query)
    corpus = [tokens(document) for document in documents]
    if not query_tokens or not any(corpus):
        return []
    scores = BM25Okapi([doc or [""] for doc in corpus]).get_scores(query_tokens)
    # "Shares a word" is checked directly and not by score: Okapi scores a word that is in every
    # document as zero or negative, so a patient with one short chunk would never match.
    wanted = set(query_tokens)
    sharing = [index for index, doc in enumerate(corpus) if wanted & set(doc)]
    return sorted(sharing, key=lambda index: (-scores[index], index))
