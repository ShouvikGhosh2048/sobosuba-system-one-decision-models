"""A decision model plays sobosuba from screenshots (image input + box questions).

Each step:
  1. send the screenshot and ask a `choice`: click (menus / buttons) or drag (gameplay)
  2. click -> ask one `box` around the button to click, then click its centre
     drag  -> ask a `box` around the loaded blob to throw (press), then send the screenshot with that blob
              outlined in white and ask a `box` around the blob to hit (release); drag between the centres

Needs OPENROUTER_API_KEY in .env; optional DECISION_MODEL (default jev-latest).

Usage:  .venv/Scripts/python decision_model_vision.py [--steps N (default 200)] [--settle S (default 2)] [--dry-run]
"""
import argparse, base64, json, os, time
import cv2, requests
from dotenv import load_dotenv
import winio

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, '.env'))
URL = 'https://openrouter.ai/api/v1/systemone'
API_KEY = os.environ['OPENROUTER_API_KEY'].strip()
MODEL = os.environ.get('DECISION_MODEL', 'jev-latest')

GAME = ('You are playing sobosuba, a physics merge puzzle, by looking at the attached {w}x{h} px screenshot of the game. '
        'Menus have buttons that you click. During gameplay, coloured numbered blobs are loaded under launchers along '
        'the top of a box: you press on a loaded blob, drag in the direction you want to throw it (an arrow shows the aim) '
        'and release. Two blobs with the same colour and number merge into one with double the number when they touch, '
        'which scores points. Unmatched blobs pile up and end the game.')

def ask(texts, questions, image):
    """texts: list of strings placed before the screenshot in `state`."""
    _, png = cv2.imencode('.png', image)
    url = 'data:image/png;base64,' + base64.b64encode(png).decode()
    req = {'model': MODEL, 'state': [*texts, {'type': 'image_url', 'image_url': {'url': url}}], 'questions': questions}
    r = requests.post(URL, timeout=60, json=req, headers={'Authorization': f'Bearer {API_KEY}'})
    if r.status_code != 200: raise RuntimeError(f'{MODEL} {r.status_code}: {r.text[:300]}')
    return r.json()

def box_center(ans, w, h):
    b = ans['box']
    return int((b['left'] + b['right']) / 2 * w), int((b['top'] + b['bottom']) / 2 * h)

def annotate(img, boxes, label):
    """Draw the model's boxes (name -> answer), their centres, and the drag arrow."""
    out = img.copy(); H, W = img.shape[:2]
    colors = {'target': (0, 255, 0), 'press': (0, 255, 255), 'release': (255, 0, 255)}
    for name, ans in boxes.items():
        b, c = ans['box'], colors.get(name, (0, 255, 0))
        cv2.rectangle(out, (int(b['left'] * W), int(b['top'] * H)), (int(b['right'] * W), int(b['bottom'] * H)), c, 2)
        cx, cy = box_center(ans, W, H); cv2.drawMarker(out, (cx, cy), c, cv2.MARKER_CROSS, 14, 2)
        cv2.putText(out, f"{name} {ans.get('confidence')}", (int(b['left'] * W), max(15, int(b['top'] * H) - 6)), 0, 0.5, c, 1)
    if 'press' in boxes and 'release' in boxes:
        cv2.arrowedLine(out, box_center(boxes['press'], W, H), box_center(boxes['release'], W, H), (255, 255, 255), 1)
    cv2.putText(out, label, (10, H - 12), 0, 0.6, (0, 255, 0), 2)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--steps', type=int, default=200)
    ap.add_argument('--settle', type=float, default=2.0, help='seconds to wait after each action so blobs can land')
    ap.add_argument('--dry-run', action='store_true', help='decide once, save the annotated screenshot, do nothing')
    a = ap.parse_args()
    try: h = winio.find()
    except RuntimeError as e: raise SystemExit(e)
    out = os.path.join(HERE, 'runs', time.strftime('%Y%m%d-%H%M%S')); os.makedirs(out); print('saving to', out)
    with open(f'{out}/log.jsonl', 'a') as log:
        play(h, a, out, log)

def play(h, a, out, log):
    for step in range(a.steps):
        if winio.in_corner(): print('mouse in corner - stopping'); break
        if not winio.is_open(h): print('game window closed - stopping'); break
        img = winio.capture(h); H, W = img.shape[:2]
        state = [GAME.format(w=W, h=H)]

        t = time.time()
        r1 = ask(state, {'action': {'type': 'choice',
            'instructions': 'Look at the screenshot. Should you click something (a menu or button) or drag (throw a blob during gameplay)?',
            'criteria': {'click': 'A menu, dialog, game-over or other screen with buttons is showing: click one.',
                         'drag': 'The game board is showing with a loaded blob at the top: drag to throw it.'}}}, img)
        act = r1['answers']['action']
        if act['choice'] == 'click':
            rs = [ask(state + ['You decided to click.'],
                      {'target': {'type': 'box', 'instructions':
                          f'In the screenshot ({W}x{H} px), draw a box tightly around the button you want to click '
                          '(e.g. the one that starts or continues the game).'}}, img)]
        else:
            # two calls: pick the blob to throw, then show it boxed on the screenshot and ask where to throw it
            rp = ask(state + ['You decided to drag: first pick the loaded blob to throw.'],
                     {'press': {'type': 'box', 'instructions':
                          f'In the screenshot ({W}x{H} px), draw a box tightly around the blob you want to throw: one '
                          'loaded blob in the row at the top of the board. Pick one that has a blob with the same colour '
                          'and number down on the board, if any does. The drag starts at the centre of this box.'}}, img)
            b = rp['answers']['press']['box']
            marked = img.copy()
            cv2.rectangle(marked, (int(b['left'] * W), int(b['top'] * H)), (int(b['right'] * W), int(b['bottom'] * H)),
                          (255, 255, 255), 3)
            rr = ask(state + ['You are throwing the blob inside the white box at the top of the screenshot. '
                              'Look at its colour and number, then pick where to throw it.'],
                     {'release': {'type': 'box', 'instructions':
                          f'In the screenshot ({W}x{H} px), draw a box tightly around the target blob: one blob that is '
                          'already down on the board (below the top row) with the same colour and number as the blob in '
                          'the white box. If none matches, pick the board blob closest in number to it. Do not pick a '
                          'blob in the top row or empty space. The drag ends at the centre of this box and the thrown '
                          'blob flies toward it.'}}, marked)
            rs = [rp, rr]
        answers = {k: v for r in rs for k, v in r['answers'].items()}
        pts = [box_center(answers[k], W, H) for k in ('target', 'press', 'release') if k in answers]
        dt = time.time() - t
        desc = f"{act['choice']} {' -> '.join(map(str, pts))}"
        print(f"step {step}: {desc} (choice conf {act.get('confidence')}, "
              f"box conf {[v.get('confidence') for v in answers.values()]}, {dt:.2f}s)")
        log.write(json.dumps({'t': time.time(), 'r1': r1, 'r2': rs, 'pts': pts}) + '\n'); log.flush()
        cv2.imwrite(f'{out}/step_{step:04d}.png',
                    annotate(img, answers, f"step {step}: {desc} (choice {act['choice']} conf {act.get('confidence')})"))
        if a.dry_run: break

        winio.wait_for_idle_mouse()
        done = winio.click(h, *pts[0]) if len(pts) == 1 else winio.drag(h, *pts[0], *pts[1])
        if not done: print('could not focus game window, retrying'); time.sleep(2); continue
        time.sleep(a.settle)

if __name__ == '__main__':
    main()
