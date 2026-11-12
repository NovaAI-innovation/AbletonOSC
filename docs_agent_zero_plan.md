# Agent Zero Extension Plan - AbletonOSC Browser & Device Loading

## Context

- Fork: NovaAI-innovation/AbletonOSC (upstream ideoforms/AbletonOSC, branch master)
- Target: Ableton Live 11 Suite on host msi (Windows), reached over Tailscale
- Goal: let Agent Zero load instruments and effects into Live, create return-track FX
  channels, and drive them - not merely manipulate devices that already exist.

## Verified constraints

1. AbletonOSC has no browser or device-load handler today (verified by reading every
   handler module: song, track, clip, clip_slot, device, scene, view, application, midimap).
2. Track.insert_device(name) is available only since Live 12.3. The target is Live 11,
   so it is NOT available. Device loading must go through the Browser API.
3. The Browser API lives in Live.Browser (app.browser, BrowserItem, browser.load_item),
   and is not covered by the official Cycling 74 LOM documentation.
4. browser.load_item(item) loads onto the currently selected track, so a handler must
   select the target track before loading.
5. BrowserItem exposes children, is_device, is_folder, is_loadable, is_selected, uri, name.
6. Existing tests are integration tests driven over OSC against a live Live instance;
   there is no Live stub. New tests must follow the same pattern.
7. Handler contract: subclass AbletonOSCHandler, register addresses in init_api() via
   self.osc_server.add_handler, then register the class in abletonosc/__init__.py,
   in manager.init_api handlers list, and in manager.reload_imports.

## Feature stages - one branch each, merge only after tests pass

### Stage 1 - Browser introspection (read-only)
Branch: feature/browser-introspection

Adds read-only addresses:
- /live/browser/get/categories - top-level category names
- /live/browser/get/children <category> [path...] - child names plus is_folder,
  is_device, is_loadable flags
- /live/browser/get/item <category> [path...] - single item metadata

Risk to verify first: whether self.application().browser is reachable from a handler.

### Stage 2 - Load items
Branch: feature/browser-load

Adds /live/browser/load_item <track_index> <category> [path...]:
- selects the target track, resolves the item, checks is_loadable, calls load_item
- replies with success and the resolved name

### Stage 3 - Return tracks and sends
Branch: feature/return-tracks

Adds querying of song.return_tracks, create/delete return tracks, and per-track
send-level read and write - required for psytrance FX channels.

### Stage 4 - Hot-swap
Branch: feature/hotswap

Exposes hotswap_target selection plus load, for in-place device replacement while
iterating on an effects chain.

## Testing approach

- Add integration tests in tests/ using the existing client fixture pattern.
- Deploy the project tree to the msi remote-scripts folder, trigger /live/api/reload,
  then run pytest against the live instance.
- Tests that load devices must remove them afterwards so the session is left clean.
- Manual check: load a real device, read it back, confirm it appears on the track.

## Merge policy

- Merge with --no-ff into master only after the stage tests pass.
- Push master and the feature branch to the fork.
- One stage at a time; do not start the next until the previous is merged.
