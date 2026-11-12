import pytest

from . import client, wait_one_tick

#--------------------------------------------------------------------------------
# Browser introspection (read-only).
# These tests exercise the handler against a live Ableton Live instance.
#--------------------------------------------------------------------------------

def test_browser_categories(client):
    categories = client.query("/live/browser/get/categories")
    assert isinstance(categories, tuple)
    assert len(categories) > 0
    # Core categories that every Live install provides.
    assert "instruments" in categories
    assert "audio_effects" in categories
    assert "midi_effects" in categories


def test_browser_instruments_children(client):
    children = client.query("/live/browser/get/children", ("instruments",))
    # Returned as a flat tuple: name, is_folder, is_device, is_loadable per child.
    assert isinstance(children, tuple)
    assert len(children) > 0
    assert len(children) % 4 == 0
    names = children[0::4]
    assert all(isinstance(name, str) and name for name in names)


def test_browser_item_metadata(client):
    children = client.query("/live/browser/get/children", ("instruments",))
    first_name = children[0]
    item = client.query("/live/browser/get/item", ("instruments", first_name))
    # name, is_folder, is_device, is_loadable, uri, source
    assert isinstance(item, tuple)
    assert len(item) == 6
    assert item[0] == first_name
    assert isinstance(item[1], bool)
    assert isinstance(item[2], bool)
    assert isinstance(item[3], bool)
    assert isinstance(item[4], str)
    assert isinstance(item[5], str)


def test_browser_deep_path(client):
    """Descend into the first folder found, if any."""
    children = client.query("/live/browser/get/children", ("instruments",))
    folder = None
    for index in range(0, len(children), 4):
        if children[index + 1]:  # is_folder
            folder = children[index]
            break
    if folder is None:
        return  # No folders at top level; nothing to descend.
    nested = client.query("/live/browser/get/children", ("instruments", folder))
    assert isinstance(nested, tuple)


def test_browser_unknown_category_rejected(client):
    # The handler raises on an unknown category; the OSC server logs the error
    # and sends no reply, so the client surfaces a timeout as RuntimeError.
    with pytest.raises(RuntimeError):
        client.query("/live/browser/get/children", ("not_a_real_category",))
