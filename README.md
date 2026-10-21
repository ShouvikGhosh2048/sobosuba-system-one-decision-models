# A decision model plays sobosuba

A decision model playing sobosuba from raw screenshots, through OpenRouter's `/api/v1/systemone` endpoint. The default is TypeSafe's Jev (`jev-latest`).

Each step:
1. `winio.capture` grabs the game window with PrintWindow.
2. A `choice` question asks whether to **click** (menus, buttons) or **drag** (gameplay).
3. For a click, one `box` question around the button to click, and the bot clicks its center.
4. For a drag, two calls. The first asks for a box around the loaded blob to throw (press). The second gets the screenshot with that blob outlined in white and asks for a box around a blob with the same colour and number down on the board (release). The bot drags between the two centers: in this game you press on a loaded blob and drag toward where you want to throw it.

Each call sends only the game description and the current screenshot; there is no history of earlier actions.

## Run

```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
# put OPENROUTER_API_KEY=... in .env
# start the sobosuba demo (any screen; the model navigates the menus itself), then:
.venv/Scripts/python decision_model_vision.py              # 200 steps (default)
.venv/Scripts/python decision_model_vision.py --steps 10   # quick test
.venv/Scripts/python decision_model_vision.py --dry-run    # one decision, nothing clicked
.venv/Scripts/python decision_model_vision.py --settle 1   # wait 1s after each action (default 2)
```

Optional: set `DECISION_MODEL` in `.env` to use a different decision model (default `jev-latest`). It must support image input and box questions.

Each run gets its own folder `runs/<timestamp>/`. It holds `log.jsonl` (every model response; `r1` is the click/drag choice, `r2` the list of box responses) and one screenshot per step, annotated with the model's boxes: green for a click, yellow for press, magenta for release.
