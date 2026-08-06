# Realtime protocol

The realtime endpoint is `/ws`, with `/api/realtime` as an equivalent route. It uses JSON messages
over WebSocket. Protocol version 2 adds revisioned snapshots, editor commands, resync, and semantic
game events. Version 1 input and frame messages remain supported.

## Hello

The server sends `hello` immediately after accepting a connection:

```json
{
  "type": "hello",
  "protocol": "sceneify-realtime",
  "version": 2,
  "capabilities": ["snapshot", "commands", "undoRedo", "semanticEvents"],
  "clientId": "opaque-id",
  "tickRate": 60.0,
  "mode": "play",
  "revision": 0,
  "scene": {}
}
```

Clients must check `protocol` and `version` before processing later messages.
`mode` is `play` for `Scene.play()` and `edit` for `Scene.run()`.

## Commands and resync

Editor mutations are atomic commands with an expected revision:

```json
{
  "type": "command",
  "revision": 4,
  "command": {
    "action": "reparent",
    "id": "crate",
    "parentId": "room"
  }
}
```

The server broadcasts a `command_ack` containing the new revision and scene. If the supplied
revision is stale, the server returns `resync`. A client can request a fresh snapshot at any time:

```json
{"type": "resync"}
```

```json
{"type": "snapshot", "revision": 5, "scene": {}}
```

## Semantic game events

The browser runs latency-sensitive controls and physics, then sends occasional semantic events to
Python:

```json
{
  "type": "semantic_event",
  "name": "collect",
  "nodeId": "coin_1",
  "data": {"score": 1}
}
```

Callbacks registered with `Scene.on_event` receive `(scene, event)`.

## Input

A client sends an action and an optional JSON value:

```json
{
  "type": "input",
  "action": "move",
  "value": [1, 0, 0],
  "metadata": {}
}
```

The server dispatches the input once to every callback registered with `Scene.on_input`. The
callback receives `(scene, event)`. `event.action`, `event.value`, `event.client_id`, and
`event.metadata` are available.

## Frame

During `Scene.play()`, the server broadcasts one frame after each shared runtime tick:

```json
{
  "type": "frame",
  "sequence": 42,
  "time": 0.7,
  "delta": 0.0167,
  "scene": {}
}
```

`sequence` is global to the runtime. Connecting more clients does not create more tick loops.
Callbacks registered with `Scene.on_tick` receive `(scene, delta_seconds)` and may be synchronous
or asynchronous.

## Ping

A client can test liveness while preserving its own timestamp:

```json
{"type": "ping", "timestamp": 123.5}
```

The server replies:

```json
{"type": "ping", "timestamp": 123.5, "reply": true}
```

Invalid messages receive an `error` object with a human readable `detail`. Callback failures are
reported to the originating input client. A tick callback failure is retained by the runtime and
does not terminate the shared loop.
