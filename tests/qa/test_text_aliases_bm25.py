from app.qa.aliases import expand_query
from app.qa.bm25 import bm25_rank
from app.qa.text import tokens

LASIX = [["furosemide", "LASIX"], ["lisinopril", "ZESTRIL"]]


def test_tokens_drop_filler_and_plural_endings():
    assert tokens("Can I take my pills with the Advil?") == ["take", "pill", "advil"]
    assert tokens("glass") == ["glass"]  # "ss" is not a plural
    assert tokens("") == []


def test_a_question_that_names_a_medicine_also_searches_its_other_names():
    assert expand_query("did they change the lasix?? why", LASIX) == (
        "did they change the lasix?? why furosemide"
    )
    assert expand_query("is furosemide ok", LASIX) == "is furosemide ok LASIX"


def test_a_question_that_names_nothing_is_left_alone():
    assert expand_query("can I shower", LASIX) == "can I shower"
    assert expand_query("anything", []) == "anything"


def test_a_name_inside_another_word_does_not_count():
    assert expand_query("what is lasixology", LASIX) == "what is lasixology"


def test_matching_passages_come_back_best_first_and_others_not_at_all():
    documents = [
        "Weigh yourself every morning",
        "Limit sodium to 2000 mg per day",
        "Take furosemide in the morning. Furosemide is a water pill.",
    ]

    assert bm25_rank(documents, "furosemide in the morning") == [2, 0]
    assert bm25_rank(documents, "zebra") == []


def test_a_question_of_only_filler_words_finds_nothing():
    assert bm25_rank(["Take it with food"], "can I do it") == []
    assert bm25_rank([], "food") == []
    assert bm25_rank(["", ""], "food") == []
