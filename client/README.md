# myClaw Harness Lab

Mac client for inspecting myClaw runs, traces, and badcase evals.

## Development

```bash
cd client
npm install
npm run dev
```

Browser preview uses mock data when it is not running inside Tauri.

## Mac App

```bash
cd client
npm run tauri -- dev
```

Build the `.app` bundle:

```bash
cd client
npm run tauri -- build
```

The bundle is generated at:

```text
client/src-tauri/target/release/bundle/macos/myClaw Harness Lab.app
```

## Current Scope

- Lists JSONL run traces from `runs/`.
- Opens one run and shows chat replay.
- Shows event timeline and raw JSON for each event.
- Runs `badcase_0001_context_memory` from the app.
- Sends one-turn interactive myClaw messages from the composer.
- Appends interactive session traces to `runs/interactive-<session>.jsonl`.
- Keeps browser preview available with mock trace data.

## Next Iterations

- Stream events while the Python turn is still running instead of refreshing after completion.
- Add per-event message/tool specialized inspectors.
- Add badcase registry and repeat-run controls.
- Add ablation labels such as `manifest=on/off`, `summary=on/off`.
- Add office sandbox file browser.
