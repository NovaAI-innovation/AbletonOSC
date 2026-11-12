import pytest

from . import client, wait_one_tick

#--------------------------------------------------------------------------------
# Browser introspection (read-only).
#
# These tests run against a live Ableton Live instance.
#
# A note on timeouts: the client's default reply timeout is TICK_DURATION (150ms),
# which suits Live's own property lookups (a tempo query answers in ~10ms). Walking
# the browser is slower, because each child is a file-system backed item: a category
# listing measured ~220ms. Every browser query below therefore passes an explicit
# timeout, or it would fail on a perfectly healthy handler.
#--------------------------------------------------------------------------------

BROWSER_TIMEOUT = 10.0


def test_browser_categories(client):
    categories = client.query("/live/browser/get/categories", (), timeout=BROWSER_TIMEOUT)
    assert isinstance(categories, tuple)
    assert len(categories) > 0
    # Core categories that every Live install provides.
    assert "instruments" in categories
    assert "audio_effects" in categories
    assert "midi_effects" in categories


def test_browser_instruments_children(client):
    children = client.query("/live/browser/get/children", ("instruments",),
                            timeout=BROWSER_TIMEOUT)
    # Returned as a flat tuple: name, is_folder, is_device, is_loadable per child.
    assert isinstance(children, tuple)
    assert len(children) > 0
    assert len(children) % 4 == 0
    names = children[0::4]
    assert all(isinstance(name, str) and name for name in names)
    # Live's own instruments are devices and therefore loadable.
    assert any(children[index + 3] for index in range(0, len(children), 4))


def test_browser_item_metadata(client):
    children = client.query("/live/browser/get/children", ("instruments",),
                            timeout=BROWSER_TIMEOUT)
    first_name = children[0]
    item = client.query("/live/browser/get/item", ("instruments", first_name),
                        timeout=BROWSER_TIMEOUT)
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
    children = client.query("/live/browser/get/children", ("instruments",),
                            timeout=BROWSER_TIMEOUT)
    folder = None
    for index in range(0, len(children), 4):
        if children[index + 1]:  # is_folder
            folder = children[index]
            break
    if folder is None:
        pytest.skip("No folders at the top level of the instruments category")
    nested = client.query("/live/browser/get/children", ("instruments", folder),
                          timeout=BROWSER_TIMEOUT)
    assert isinstance(nested, tuple)


def test_browser_unknown_category_rejected(client):
    # The handler raises on an unknown category; the OSC server logs the error and
    # sends no reply, so the client surfaces the silence as a timeout.
    with pytest.raises(RuntimeError):
        client.query("/live/browser/get/children", ("not_a_real_category",), timeout=2.0)
