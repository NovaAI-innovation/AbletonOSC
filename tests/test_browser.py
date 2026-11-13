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

#--------------------------------------------------------------------------------
# Loading (Stage 2). This is the one write path in the handler.
#--------------------------------------------------------------------------------


def _device_names(client, track_index):
    """Device names on a track, as a list. Reply shape is (track_index, *names)."""
    rv = client.query("/live/track/get/devices/name", (track_index,),
                      timeout=BROWSER_TIMEOUT)
    return list(rv[1:]) if rv else []


def test_browser_load_item_adds_and_removes_device(client):
    """Load a real instrument, confirm it landed, then remove it again.

    The test cleans up after itself so a test run does not leave devices behind
    in the user's session.
    """
    track_index = 0

    # Pick the first loadable instrument the browser offers, rather than hardcoding
    # a device name: this stays valid on any Live install and any content version.
    children = client.query("/live/browser/get/children", ("instruments",),
                            timeout=BROWSER_TIMEOUT)
    target = None
    for index in range(0, len(children), 4):
        name, is_folder, is_device, is_loadable = children[index:index + 4]
        if is_loadable and is_device:
            target = name
            break
    assert target is not None, "no loadable instrument found in the browser"

    before = _device_names(client, track_index)

    track_out, loaded_name, uri = client.query(
        "/live/browser/load_item", (track_index, "instruments", target),
        timeout=BROWSER_TIMEOUT,
    )
    assert track_out == track_index
    assert loaded_name == target
    assert uri

    after = _device_names(client, track_index)
    assert len(after) == len(before) + 1, "device was not added to the track"
    assert loaded_name in after

    # Clean up: remove the device we just added so the session is left as we found it.
    device_index = after.index(loaded_name)
    client.send_message("/live/track/delete_device", (track_index, device_index))
    wait_one_tick()
    wait_one_tick()

    final = _device_names(client, track_index)
    assert final == before, "cleanup did not restore the original device list"


def test_browser_load_item_rejects_unloadable(client):
    """A folder is not loadable and must be refused rather than silently ignored."""
    children = client.query("/live/browser/get/children", ("instruments",),
                            timeout=BROWSER_TIMEOUT)
    folder = None
    for index in range(0, len(children), 4):
        name, is_folder = children[index], children[index + 1]
        if is_folder:
            folder = name
            break
    if folder is None:
        pytest.skip("No folder at the top level of the instruments category")

    with pytest.raises(RuntimeError):
        client.query("/live/browser/load_item", (0, "instruments", folder), timeout=2.0)
