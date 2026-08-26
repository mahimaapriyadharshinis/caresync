from ambulance.router import choose_hospital, rank_hospitals


def test_chooses_hospital_with_most_remaining_capacity():
    states = {
        "hospA": {"icu_beds": 2},
        "hospB": {"icu_beds": 7},
        "hospC": {"icu_beds": 0},
    }
    assert choose_hospital(states, "icu_beds") == "hospB"


def test_never_recommends_a_hospital_at_zero():
    """The exact failure mode from the project's motivation slide."""
    states = {"hospA": {"icu_beds": 0}, "hospB": {"icu_beds": 0}}
    assert choose_hospital(states, "icu_beds") is None


def test_ignores_hospitals_that_never_reported_the_resource():
    states = {"hospA": {"er_capacity": 5}, "hospB": {"icu_beds": 3}}
    assert choose_hospital(states, "icu_beds") == "hospB"


def test_rank_hospitals_orders_best_first_and_excludes_zero():
    states = {
        "hospA": {"icu_beds": 2},
        "hospB": {"icu_beds": 7},
        "hospC": {"icu_beds": 0},
    }
    ranked = rank_hospitals(states, "icu_beds")
    assert ranked == [("hospB", 7), ("hospA", 2)]


def test_empty_state_recommends_nothing():
    assert choose_hospital({}, "icu_beds") is None
    assert rank_hospitals({}, "icu_beds") == []
