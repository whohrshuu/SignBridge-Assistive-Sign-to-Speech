# SignBridge — gesture reliability update

## Run locally on Windows / VS Code
Extract the ZIP into a new folder. Open `SignBridge-Production-MVP` in VS Code and run:
```cmd
python server.py
```
Open **http://localhost:8000** in Chrome or Edge. Choose **Start Project → Launch App → Start Camera**. Keep the terminal open. Python 3.10+ is recommended; no pip packages are required for this local mode. Tracking/model files are bundled, so camera recognition does not need a CDN. Speech voices depend on the browser/OS.

## I Need Assistance — corrected
Show **both palms facing the camera**, with four fingers extended on each hand. Keep the hands slightly apart so neither covers the other. Thumbs can be open, relaxed or tucked. Hold for about **0.6 seconds after both hands are detected**.

The screen must show **2 hands** and then **I Need Assistance**. In Instant speech mode it speaks once. Lower both hands for about half a second before repeating. If only one hand is detected, move farther from the camera and keep all fingers inside the frame. A quick-phrase button is also available.

## All existing mappings
These are **custom communication shortcuts**, not official ASL word translations.

| Pose | Output |
|---|---|
| Thumb up, other fingers curled | Yes |
| Thumb down, other fingers curled | No |
| One open palm, thumb extended | Hello |
| Closed fist | Stop |
| Index finger only, thumb tucked | Help |
| Index and middle parallel, thumb tucked | Water |
| Index/middle/ring extended, thumb tucked | Food |
| Four fingers extended, thumb tucked | Thank You |
| Thumb and pinky extended | Call |
| Index and middle spread into V, thumb tucked | Wait |
| Two open four-finger palms (thumbs may relax) | I Need Assistance |
| Fist + open palm | Emergency |
| Open palm + two parallel fingers | Please Wait |
| Open palm + thumb up | Call Family |

Either hand order works for every combination. Single-hand phrases require about 0.85 seconds to give the second hand time to enter. Hold a pose until accepted; it will not repeat continuously. Unsupported two-hand combinations show Unknown rather than falling back to a single-hand phrase.

## Improvements
- Shared gesture engine for local and deployed app.
- Joint-angle and palm-relative geometry instead of fixed image-coordinate finger/gap thresholds; camera aspect ratio is accounted for.
- Relaxed-thumb recognition for two-hand open palms.
- Two-hand combinations get priority, with time-based dwell and short tracking-dropout tolerance.
- Speech no longer silently drops a new phrase because another phrase was just spoken.
- Guarded camera start/stop and no duplicate processing of the same video frame.
- Bundled MediaPipe Hands 0.4.1675469240 and drawing utilities 0.3.1675466124.
- Deployment frontend and API served together; no separate Cloudflare frontend required.

## Tests and limits
`node tests/test_gestures.cjs` checks 540 synthetic transformed poses, all 14 mappings, relaxed thumbs, unknown hands, and timing/repeat behavior.

Local API tests:
```cmd
python -m unittest discover -s tests -p test_server.py -v
```
Full backend/deployment tests (install requirements first):
```cmd
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```
Eight Python tests and the JavaScript tests passed. Browser testing loaded the bundled camera runtime and verified assistance text, one speech event and no duplicate phrase, using injected test landmarks. Those are software checks, **not real-person gesture accuracy measurements**. Check the poses on your own webcam before presenting or deploying. No computer-vision system can guarantee recognition for every hand, lighting condition and occlusion.

## Deployment
Read **PRODUCTION_SETUP.md** for the simplified **Render + Supabase** setup. `api.py` serves the authenticated frontend and private APIs on one HTTPS address. Local `server.py` is not the public deployment server. The package is not yet live: your hosting and Supabase configuration are still required.

Your local samples/history remain in `data/signbridge.sqlite3`. Back up or export your old dataset before replacing folders; use the fresh extracted folder to avoid old scripts being mixed with the update. Supabase stores each signed-in user's cloud data separately using the included row-level policies.
