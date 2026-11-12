import Live
from typing import Tuple, Any
from .handler import AbletonOSCHandler

#--------------------------------------------------------------------------------
# Read-only access to Live's content browser.
#
# The Browser API lives in Live.Browser and is not covered by the official
# Cycling 74 LOM documentation. It is reached via the Application object.
#
# This handler is intentionally read-only: it lets a client discover what the
# browser contains before anything is loaded onto a track.
#--------------------------------------------------------------------------------

# Categories exposed by the Browser object. Each maps to either a single
# BrowserItem or a list of BrowserItems (see Browser.get_* in the Live API).
SINGLE_ITEM_CATEGORIES = (
    "audio_effects",
    "clips",
    "current_project",
    "drums",
    "instruments",
    "max_for_live",
    "midi_effects",
    "packs",
    "plugins",
    "samples",
    "sounds",
    "user_library",
)

LIST_CATEGORIES = (
    "colors",
    "legacy_libraries",
    "user_folders",
)


def _item_flags(item) -> Tuple[Any, ...]:
    """(name, is_folder, is_device, is_loadable) for one BrowserItem."""
    return (
        item.name,
        bool(item.is_folder),
        bool(item.is_device),
        bool(item.is_loadable),
    )


class BrowserHandler(AbletonOSCHandler):
    def __init__(self, manager):
        super().__init__(manager)
        self.class_identifier = "browser"

    #--------------------------------------------------------------------------------
    # Helpers
    #--------------------------------------------------------------------------------
    def _get_browser(self):
        return Live.Application.get_application().browser

    def _resolve_category(self, category: str):
        """Return the root object for a category name, or None if unknown."""
        browser = self._get_browser()
        if category in SINGLE_ITEM_CATEGORIES:
            return getattr(browser, category)
        if category in LIST_CATEGORIES:
            # A list of roots; expose it as a plain Python list.
            return list(getattr(browser, category))
        return None

    @staticmethod
    def _walk(root, path):
        """Descend `path` from `root`. Returns the item or None."""
        item = root
        for segment in path:
            if item is None:
                return None
            children = list(getattr(item, "children", ()) or ())
            match = None
            for child in children:
                if child.name == segment:
                    match = child
                    break
            item = match
        return item

    #--------------------------------------------------------------------------------
    # API
    #--------------------------------------------------------------------------------
    def init_api(self):
        def get_categories(_) -> Tuple:
            browser = self._get_browser()
            available = []
            for name in SINGLE_ITEM_CATEGORIES + LIST_CATEGORIES:
                try:
                    if getattr(browser, name, None) is not None:
                        available.append(name)
                except Exception:
                    # Some categories may be absent on older Live versions.
                    continue
            return tuple(available)
        self.osc_server.add_handler("/live/browser/get/categories", get_categories)

        def get_children(params: Tuple[Any, ...]) -> Tuple:
            if len(params) < 1:
                raise ValueError("get/children requires at least a category argument")
            category = str(params[0])
            path = tuple(str(p) for p in params[1:])
            root = self._resolve_category(category)
            if root is None:
                raise ValueError("Unknown browser category: %s" % category)
            # LIST_CATEGORIES return several roots; expose them as a synthetic level.
            if isinstance(root, list):
                if not path:
                    return tuple(
                        value
                        for index, item in enumerate(root)
                        for value in ((str(index),) + _item_flags(item))
                    )
                try:
                    root = root[int(path[0])]
                except (ValueError, IndexError):
                    raise ValueError("Invalid index %r for category %s" % (path[0], category))
                path = path[1:]
            item = self._walk(root, path)
            if item is None:
                raise ValueError("Path not found in category %s" % category)
            return tuple(value for child in list(item.children or ()) for value in _item_flags(child))
        self.osc_server.add_handler("/live/browser/get/children", get_children)

        def get_item(params: Tuple[Any, ...]) -> Tuple:
            if len(params) < 1:
                raise ValueError("get/item requires at least a category argument")
            category = str(params[0])
            path = tuple(str(p) for p in params[1:])
            root = self._resolve_category(category)
            if root is None:
                raise ValueError("Unknown browser category: %s" % category)
            if isinstance(root, list):
                if not path:
                    raise ValueError("Category %s is a list; supply an index" % category)
                try:
                    root = root[int(path[0])]
                except (ValueError, IndexError):
                    raise ValueError("Invalid index %r for category %s" % (path[0], category))
                path = path[1:]
            item = self._walk(root, path)
            if item is None:
                raise ValueError("Path not found in category %s" % category)
            return _item_flags(item) + (str(item.uri), str(getattr(item, "source", "")))
        self.osc_server.add_handler("/live/browser/get/item", get_item)
