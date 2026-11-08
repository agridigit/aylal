"""T013 - G6: schemas are extra=forbid; storage keys and URLs are never accepted from clients; key patterns."""
import re
import uuid

import pytest
from pydantic import ValidationError

OK = {"id": str(uuid.uuid4()), "note": "feuilles jaunes"}


def _model():
    from app.monitoring.schemas import ObservationInput

    return ObservationInput


def test_given_a_valid_observation_then_it_is_accepted_with_or_without_an_opaque_photo_id():
    _model().model_validate(OK)
    _model().model_validate({**OK, "photo_id": str(uuid.uuid4())})


@pytest.mark.parametrize("extra", [{"photo_key": "farms/x/zone-photos/y"}, {"map_key": "farms/x/vigor/y.png"},
                                   {"raster_key": "r"}, {"url": "https://evil.test/x"}, {"author_id": str(uuid.uuid4())},
                                   {"farm_id": str(uuid.uuid4())}, {"status": "resolved"}])
def test_given_a_storage_key_url_or_server_field_in_the_body_then_it_is_refused(extra):
    _model().model_validate(OK)
    with pytest.raises(ValidationError):
        _model().model_validate({**OK, **extra})


def test_given_a_url_as_photo_id_then_it_is_refused():
    with pytest.raises(ValidationError):
        _model().model_validate({**OK, "photo_id": "https://evil.test/x"})


def test_given_the_note_length_then_500_passes_and_501_is_refused():
    _model().model_validate({**OK, "note": "x" * 500})
    with pytest.raises(ValidationError):
        _model().model_validate({**OK, "note": "x" * 501})


def test_given_server_keys_then_they_match_the_documented_patterns():
    from app.monitoring.uploads import vigor_map_key, zone_photo_key

    farm, obj = uuid.uuid4(), uuid.uuid4()
    assert re.fullmatch(rf"farms/{farm}/vigor/{obj}\.png", vigor_map_key(farm, obj))
    assert re.fullmatch(rf"farms/{farm}/zone-photos/{obj}", zone_photo_key(farm, obj))
