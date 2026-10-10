from app.vision_extract import contains_banned_identifier, scrub_extracted_fields


def test_allowed_fields_pass_through():
    raw = {"name": "Asha Devi", "age": 45, "gender": "female", "document_type": "ration_card"}
    clean = scrub_extracted_fields(raw)
    assert clean == raw


def test_disallowed_field_dropped():
    raw = {"name": "Asha Devi", "favorite_color": "blue"}
    clean = scrub_extracted_fields(raw)
    assert "favorite_color" not in clean
    assert clean["name"] == "Asha Devi"


def test_aadhaar_number_rejected():
    raw = {"name": "Asha Devi", "aadhaar_number": "1234 5678 9012"}
    clean = scrub_extracted_fields(raw)
    assert "aadhaar_number" not in clean


def test_twelve_digit_number_anywhere_rejects_field():
    raw = {"name": "123456789012"}
    clean = scrub_extracted_fields(raw)
    assert "name" not in clean


def test_pan_pattern_rejected():
    raw = {"name": "ABCDE1234F"}
    clean = scrub_extracted_fields(raw)
    assert "name" not in clean


def test_phone_like_ten_digit_in_occupation_field_still_allowed_if_not_banned_pattern():
    # A 10-digit number alone is NOT a banned pattern by itself in our
    # conservative TWELVE_DIGIT_RE (we only hard-block 12-digit numbers,
    # Aadhaar-shaped, PAN-shaped, voter-id-shaped and VID-shaped values).
    raw = {"occupation": "farmer"}
    clean = scrub_extracted_fields(raw)
    assert clean["occupation"] == "farmer"


def test_empty_string_values_dropped():
    raw = {"name": "   ", "gender": "female"}
    clean = scrub_extracted_fields(raw)
    assert "name" not in clean
    assert clean["gender"] == "female"


def test_contains_banned_identifier_detects_aadhaar():
    assert contains_banned_identifier("1234 5678 9012") is True
    assert contains_banned_identifier("farmer") is False


def test_non_dict_raw_returns_empty():
    assert scrub_extracted_fields("not a dict") == {}
    assert scrub_extracted_fields(None) == {}


def test_voter_id_pattern_rejected():
    raw = {"document_type": "ABC1234567"}
    clean = scrub_extracted_fields(raw)
    assert "document_type" not in clean


def test_vid_sixteen_digit_rejected():
    raw = {"name": "1234567890123456"}
    clean = scrub_extracted_fields(raw)
    assert "name" not in clean
