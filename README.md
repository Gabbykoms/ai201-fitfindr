# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Given a natural language query, FitFindr searches mock thrift listings, suggests outfit combinations using the user's existing wardrobe, and generates a shareable caption for the look.

## Project Structure

```
ai201-fitfindr/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tests/
│   └── test_tools.py          # 12 pytest tests covering all tools and failure modes
├── tools.py                   # The three required tools
├── agent.py                   # Planning loop (run_agent)
├── app.py                     # Gradio UI
├── conftest.py                # pytest path setup
├── planning.md                # Spec written before implementation
└── requirements.txt
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root (never commit this):
```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com) — no credit card required.

**Run the app:**
```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

**Run tests:**
```bash
pytest tests/
```

---

## Tool Inventory

### `search_listings`

**Purpose:** Searches the mock listings dataset for items matching a natural language description, with optional size and price filters. Scores each listing by keyword overlap and returns results sorted by relevance.

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Keywords describing the item (e.g. "vintage graphic tee"). Matched against title, description, category, style_tags, colors, and brand. |
| `size` | `str \| None` | Size string to filter by (e.g. "M", "W30 L30"). Case-insensitive contains match. Pass `None` to skip size filtering. |
| `max_price` | `float \| None` | Maximum price inclusive. Pass `None` to skip price filtering. |

**Returns:** `list[dict]` — matching listing dicts sorted by relevance score descending. Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches — never raises an exception.

---

### `suggest_outfit`

**Purpose:** Given a thrifted item and the user's wardrobe, calls the Groq LLM to suggest one or more complete outfit combinations. Falls back to general styling advice when the wardrobe is empty.

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A listing dict (the item the user is considering buying). |
| `wardrobe` | `dict` | A wardrobe dict with an `items` key containing a list of wardrobe item dicts. May be empty. |

**Returns:** `str` — a non-empty outfit suggestion. When `wardrobe["items"]` is empty, returns general styling advice for the item alone. On LLM failure, returns a descriptive error string starting with "Could not generate outfit suggestion".

---

### `create_fit_card`

**Purpose:** Calls the Groq LLM to write a short, casual, shareable caption (Instagram/TikTok style) for the complete outfit. Uses temperature 1.0 to ensure varied output across calls.

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string returned by `suggest_outfit`. Must be non-empty. |
| `new_item` | `dict` | The listing dict for the thrifted item — used to pull title, price, and platform into the caption. |

**Returns:** `str` — a 2–4 sentence caption mentioning the item name, price, and platform once each. If `outfit` is empty or whitespace, returns `"Cannot create fit card: outfit description is missing."` immediately without calling the LLM. On LLM failure, returns a descriptive error string.

---

## How the Planning Loop Works

`run_agent()` in `agent.py` runs a sequential, conditionally gated loop. Each step only executes if the previous one succeeded:

1. **Parse the query.** Regex extracts `size` (e.g. "size M") and `max_price` (any dollar amount) from the raw query string. The description is what remains after stripping those tokens. This approach was chosen over an LLM parse to keep the step fast and deterministic.

2. **Call `search_listings`.** If the result is an empty list, `session["error"]` is set to a message explaining what was searched and what the user can try differently. The function returns immediately — `suggest_outfit` and `create_fit_card` are never called with empty input.

3. **Select the top result.** `session["selected_item"] = results[0]`.

4. **Call `suggest_outfit`.** If the response starts with "Could not", the agent sets `session["error"]` and returns early without calling `create_fit_card`.

5. **Call `create_fit_card`.** Result stored in `session["fit_card"]`.

6. **Return the session dict.** `app.py` reads the final session to populate the three output panels.

The key invariant: **no tool is called with the output of a failed previous tool.** The agent branches on results, not on a fixed sequence.

---

## State Management

All state lives in a single `session` dict created at the start of each `run_agent()` call. No tool receives a raw query string — each receives exactly what the previous step produced.

| Key | Type | Set by | Used by |
|-----|------|--------|---------|
| `query` | `str` | initialization | logging |
| `parsed` | `dict` | query parsing step | `search_listings` |
| `search_results` | `list[dict]` | `search_listings` | planning loop (empty check) |
| `selected_item` | `dict` | planning loop | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | `dict` | initialization | `suggest_outfit` |
| `outfit_suggestion` | `str` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `str` | `create_fit_card` | UI panel 3 |
| `error` | `str \| None` | any failure step | UI panel 1 (if set) |

`app.py` reads the final session dict and maps it to the three Gradio output panels — it never re-queries the user between steps.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the query | Returns `[]` without raising. Planning loop sets `session["error"]` = "No listings found for '[description]' in size [size] under $[price]. Try a broader description, remove the size filter, or raise your price limit." Returns the session immediately — `suggest_outfit` is never called. |
| `suggest_outfit` | Wardrobe is empty | Detects `wardrobe["items"] == []` before building the LLM prompt and switches to a general styling advice prompt. Returns a useful string — never crashes or returns empty. LLM exceptions are caught and returned as a "Could not generate outfit suggestion" error string. |
| `create_fit_card` | Outfit input is empty string | Guards at the top of the function: if `outfit` is empty or whitespace, immediately returns `"Cannot create fit card: outfit description is missing."` without touching the LLM. LLM exceptions are caught and returned as a "Fit card generation failed" error string. |

**Concrete example from testing:**

```
$ python -c "from tools import create_fit_card, search_listings; \
  results = search_listings('vintage graphic tee', size=None, max_price=50); \
  print(create_fit_card('', results[0]))"

Cannot create fit card: outfit description is missing.
```

The function returned a descriptive string with no exception, in under 1ms (no LLM call made).

---

## Interaction Walkthrough

**User query:** `"looking for a vintage graphic tee under $30"`

**Step 1 — Tool called: `search_listings`**
- Input: `description="looking for vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why this tool: It's always the first step — the agent needs a real listing before it can suggest an outfit or write a caption.
- Output: A list of matching listings sorted by relevance. Top result: `Y2K Baby Tee — Butterfly Print, $18.00, depop, excellent condition`.

**Step 2 — Tool called: `suggest_outfit`**
- Input: `new_item={"title": "Y2K Baby Tee...", "price": 18.0, ...}`, `wardrobe=get_example_wardrobe()`
- Why this tool: `search_listings` returned a result, so `session["selected_item"]` is set. The next step in the loop is always to suggest how to wear it.
- Output: "Pair this with your baggy straight-leg jeans and chunky white sneakers for a 90s look. Alternatively, try it with wide-leg khaki trousers and black combat boots for a cottagecore-grunge mix."

**Step 3 — Tool called: `create_fit_card`**
- Input: `outfit="Pair this with your baggy straight-leg jeans..."`, `new_item={"title": "Y2K Baby Tee...", "price": 18.0, "platform": "depop", ...}`
- Why this tool: Both previous tools succeeded and produced valid output. The final step is always to generate a shareable caption from the complete outfit.
- Output: "thrifted this y2k baby tee off depop for $18 and it was literally made for wide-legs 🖤 rolled the sleeves, tucked the front — full look in my stories."

**Final output to user:** Three panels populate: (1) listing summary with title, price, condition, size, style tags; (2) the outfit suggestion paragraph; (3) the fit card caption.

---

## Spec Reflection

**One way `planning.md` helped during implementation:**

The architecture diagram in `planning.md` was the most directly useful artifact. When implementing `run_agent()`, the diagram's explicit error branches ("results == []? → YES → set error → return") meant the conditional logic translated almost line-for-line into code. Without it, it would have been easy to write a loop that calls all three tools unconditionally and only checks for errors at the end — which would have caused `suggest_outfit` to receive empty input on the no-results path.

**One divergence from the spec, and why:**

The spec described using an LLM to parse the query (extract description, size, max_price). During implementation, regex was used instead. The LLM approach would have added a third API call per query (slower and costlier) for a parsing task that regex handles reliably given the constrained input format — size is always "size X" and price is always a dollar amount. The tradeoff is that queries with unusual phrasing (e.g. "something for a medium-sized person") won't extract size correctly, but for the scope of this project the regex approach is faster, cheaper, and deterministic.

---

## AI Usage

**Instance 1 — Implementing `search_listings`:**

Input given to Claude: the Tool 1 spec block from `planning.md` (what it does, all three input parameters with types, return value description, failure mode) plus the `load_listings()` function signature from `data_loader.py`.

What it produced: a working implementation that filtered by price and size and scored by keyword overlap.

What was revised: the generated scoring function only searched `title` and `style_tags`. Before using it, the spec was checked — it called for matching across title, description, category, style_tags, colors, and brand. The searchable string was expanded to include all six fields, which significantly improved recall for queries like "black boots" (colors weren't being matched).

**Instance 2 — Implementing the planning loop:**

Input given to Claude: the full architecture diagram from `planning.md` plus the Planning Loop and State Management sections, along with the existing `_new_session()` dict structure from `agent.py`.

What it produced: a planning loop implementation that called all three tools sequentially.

What was revised: the generated code did not gate `suggest_outfit` on the result of `search_listings` — it called all three tools unconditionally and only returned the error at the end. This was caught by reviewing the diagram's error branch before running the code. The early-return logic (`if not results: session["error"] = ...; return session`) was added manually to match the spec's conditional branching requirement.
