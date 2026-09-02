import monitor

LIVE_TOKENS = {
    "do-allmodel", "do-n", "do-available-now", "do-in-transit", "do-arriving-soon",
    "do-wa", "do-vic", "do-nsw", "do-qld", "do-sa", "do-act", "do-nt", "do-tas",
    "do-atto-1", "do-atto-2", "do-atto-3", "do-seal", "do-seal-6", "do-seal-6-touring",
    "do-sealion-5", "do-sealion-6", "do-sealion-7", "do-sealion-8", "do-shark-6", "do-dolphin",
    "do-essential", "do-premium", "do-performance", "do-dynamic", "do-dynamicawd",
    "do-dynamicfwd", "do-dynamiccabchassis", "do-dynamicextended", "do-premiumextended",
    "do-premiumawd",
    "do-15steel", "do-16alloy", "do-17alloy", "do-17alloywheels", "do-18alloy",
    "do-18alloywheels", "do-18blackalloy", "do-19alloywheels", "do-20alloy",
    "do-20alloywheels", "do-21alloy",
    "do-apricitywhite", "do-arcticblue", "do-arcticwhite", "do-atlantisgrey",
    "do-aurorawhite", "do-black", "do-blackbrown", "do-blackgrey", "do-bluegrey",
    "do-cosmosblack", "do-darkaquamarine", "do-deepseablue", "do-greatwhite",
    "do-greyblack", "do-harbourgrey", "do-mistgrey", "do-outbackorange", "do-pinelime",
    "do-ridgegrey", "do-sagegreen", "do-sharkgrey", "do-skiwhite", "do-stonegrey",
    "do-thaumasblack", "do-tidalblack",
}


def test_catalogs_are_disjoint():
    assert monitor.MODEL_TOKENS & monitor.COLOUR_TOKENS == set()
    assert monitor.MODEL_TOKENS & monitor.VARIANT_TOKENS == set()
    assert monitor.MODEL_TOKENS & set(monitor.STATE_NAMES) == set()


def test_every_live_token_resolves_to_a_known_category():
    for tok in LIVE_TOKENS:
        resolved = (
            tok in monitor.MODEL_TOKENS
            or tok in monitor.COLOUR_TOKENS
            or tok in monitor.STATE_NAMES
            or tok in monitor.VARIANT_TOKENS
            or tok in monitor.STATUS_TOKENS
            or tok in monitor.MISC_TOKENS
            or monitor.WHEEL_RE.match(tok) is not None
        )
        assert resolved, f"Unresolved token: {tok}"


def test_model_of_maps_token():
    card = {"state": ["do-allmodel", "do-atto-2", "do-vic"]}
    assert monitor.model_of(card) == "Atto 2"


def test_model_of_falls_back_to_unknown():
    card = {"state": ["do-allmodel", "do-vic"]}
    assert monitor.model_of(card) == "Unknown"


def test_colour_of_maps_token():
    card = {"state": ["do-allmodel", "do-thaumasblack", "do-wa"]}
    assert monitor.colour_of(card) == "Thaumas Black"


def test_colour_of_falls_back_to_unknown():
    card = {"state": ["do-allmodel", "do-atto-2", "do-wa"]}
    assert monitor.colour_of(card) == "Unknown"


def test_parse_cards_extracts_model_and_colour():
    html = (
        "<html><body>"
        '<div class="col vehicle mt-0 1001 do-allmodel do-atto-2 do-dynamic '
        'do-thaumasblack do-available-now do-wa">'
        "<h3 class=\"card-title text-nowrap\">BYD ATTO 2</h3>"
        '<h6 class="card-subtitle text-muted">Dynamic</h6>'
        '<span class="d-block text-muted fs-small">In-stock #1001</span>'
        "</div></body></html>"
    )
    cards = monitor.parse_cards(html)
    assert len(cards) == 1
    assert cards[0]["model"] == "Atto 2"
    assert cards[0]["colour"] == "Thaumas Black"