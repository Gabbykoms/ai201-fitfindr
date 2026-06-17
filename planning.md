# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Loads all mock listings and filters them against the user's query. It scores each listing by keyword overlap with the description, applies optional size and price filters, and returns the matching items sorted by relevance score (highest first).

**Input parameters:**
- `description` (str): A natural language description of the item the user is looking for (e.g. "vintage graphic tee"). Used for keyword matching against each listing's title, description, style_tags, category, colors, and brand.
- `size` (str | None): The user's size (e.g. "M", "W30 L30"). If provided, only listings whose `size` field matches are returned. If None, size is not filtered.
- `max_price` (float | None): The maximum price the user is willing to pay. If provided, only listings with `price <= max_price` are returned. If None, price is not filtered.

**What it returns:**
A list of listing dicts, each containing: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str). The list is sorted by relevance score descending. Returns an empty list `[]` if no listings match.

**What happens if it fails or returns nothing:**
If the result is an empty list, the agent sets `session["error"]` to a message explaining what was searched and suggesting the user try a broader description, remove the size filter, or raise the price limit. The agent returns immediately and does not call `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Sends a prompt to the Groq LLM (llama-3.3-70b-versatile) asking it to suggest one or more complete outfit combinations using the new thrifted item and the pieces already in the user's wardrobe. If the wardrobe is empty, it falls back to general styling advice for the item alone.

**Input parameters:**
- `new_item` (dict): A single listing dict (the top result from `search_listings`) containing at minimum `title`, `category`, `style_tags`, `colors`, `price`, and `platform`.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str, optional).

**What it returns:**
A non-empty string with one or more outfit suggestions. When the wardrobe has items, suggestions reference specific pieces by name. When the wardrobe is empty, the string provides general styling advice for the new item based on its style tags and colors.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool does not crash — it builds a different prompt asking for general styling advice and returns that. If the LLM call raises an exception, the tool catches it and returns a descriptive error string (e.g. "Could not generate outfit suggestion — LLM unavailable.") so the agent can surface it to the user.

---

### Tool 3: create_fit_card

**What it does:**
Sends a prompt to the Groq LLM asking it to write a short, casual, shareable caption (the kind you'd post on Instagram or TikTok) for the complete outfit. The prompt includes the outfit suggestion, the item's title, price, and platform, and instructs the model to sound authentic rather than like a product description.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. Must be non-empty.
- `new_item` (dict): The listing dict for the thrifted item, used to pull `title`, `price`, and `platform` into the caption.

**What it returns:**
A 2–4 sentence caption string written in casual first-person voice. It mentions the item name, price, and platform exactly once each and reads like something worth actually posting. Output varies across calls for the same input (higher LLM temperature ensures this).

**What happens if it fails or returns nothing:**
If `outfit` is an empty string, the tool returns a descriptive error string immediately without calling the LLM (e.g. "Cannot create fit card: outfit description is missing."). If the LLM call raises an exception, the tool catches it and returns a descriptive error string rather than propagating the exception.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` executes steps sequentially and gates each step on the result of the previous one:

1. **Parse the query.** Extract `description`, `size`, and `max_price` from the raw user query string using a simple LLM call or regex. Store the parsed values in `session["parsed"]`.

2. **Call `search_listings`.** Pass `session["parsed"]["description"]`, `session["parsed"]["size"]`, and `session["parsed"]["max_price"]`. Store the result in `session["search_results"]`.

3. **Check for empty results.** If `session["search_results"] == []`, set `session["error"] = "No listings found for '<description>'..."` and return the session immediately. Do NOT proceed to step 4.

4. **Select the top item.** Set `session["selected_item"] = session["search_results"][0]`. This is the item passed to all subsequent tools.

5. **Call `suggest_outfit`.** Pass `session["selected_item"]` and `session["wardrobe"]`. Store the result in `session["outfit_suggestion"]`.

6. **Check for outfit error.** If `session["outfit_suggestion"]` starts with "Could not" or is empty, set `session["error"]` and return early. Do NOT call `create_fit_card` with bad input.

7. **Call `create_fit_card`.** Pass `session["outfit_suggestion"]` and `session["selected_item"]`. Store the result in `session["fit_card"]`.

8. **Return the session.** The caller reads `session["fit_card"]`, `session["outfit_suggestion"]`, and `session["selected_item"]` to populate the UI panels.

---

## State Management

**How does information from one tool get passed to the next?**

All state is stored in a single `session` dict created at the start of `run_agent()` via `_new_session()`. The dict holds every piece of information produced during the interaction:

| Key | Type | Set by | Used by |
|-----|------|--------|---------|
| `query` | str | initialization | logging / display |
| `parsed` | dict | query parsing step | `search_listings` |
| `search_results` | list[dict] | `search_listings` | planning loop (empty check) |
| `selected_item` | dict | planning loop (step 4) | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | dict | initialization (passed in) | `suggest_outfit` |
| `outfit_suggestion` | str | `suggest_outfit` | `create_fit_card` |
| `fit_card` | str | `create_fit_card` | UI output panel |
| `error` | str \| None | any failure step | UI (shown in listing panel if set) |

No tool receives a raw query string — each tool receives exactly what the previous step produced. `app.py` reads from the final session dict to populate the three output panels; it never re-queries the user between steps.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"]` to "No listings found for '[description]' in size [size] under $[max_price]. Try a broader description, remove the size filter, or raise your price limit." Return session immediately without calling further tools. |
| suggest_outfit | Wardrobe is empty | Build a different LLM prompt asking for general styling advice for the item alone (no wardrobe references). Return that advice string — do not crash or return empty. |
| create_fit_card | Outfit input is empty string | Return "Cannot create fit card: outfit description is missing." immediately without calling the LLM. If LLM raises an exception, catch it and return "Fit card generation failed — please try again." |

---

## Architecture

```
User query + wardrobe choice
          │
          ▼
    app.py: handle_query()
          │  selects wardrobe (example or empty)
          ▼
    agent.py: run_agent(query, wardrobe)
          │
          ├─ Step 1: parse query → session["parsed"]
          │          {description, size, max_price}
          │
          ├─ Step 2: search_listings(description, size, max_price)
          │               │
          │        results == []?
          │          ├── YES → session["error"] = "No listings found..."
          │          │              └──► return session  (early exit)
          │          │
          │          └── NO  → session["search_results"] = [item, ...]
          │                     session["selected_item"]  = results[0]
          │
          ├─ Step 3: suggest_outfit(selected_item, wardrobe)
          │               │
          │        wardrobe["items"] == []?
          │          ├── YES → LLM prompt: general styling advice
          │          └── NO  → LLM prompt: specific outfit combos
          │               │
          │        LLM error? → return "Could not generate outfit suggestion..."
          │               │
          │         session["outfit_suggestion"] = "..."
          │
          ├─ Step 4: create_fit_card(outfit_suggestion, selected_item)
          │               │
          │        outfit == ""?
          │          ├── YES → return "Cannot create fit card: outfit description is missing."
          │          └── NO  → LLM prompt: casual Instagram-style caption
          │               │
          │        LLM error? → return "Fit card generation failed — please try again."
          │               │
          │         session["fit_card"] = "..."
          │
          └─► return session
                    │
                    ▼
          app.py maps session → 3 output panels
            panel 1: selected_item summary  (or session["error"])
            panel 2: session["outfit_suggestion"]
            panel 3: session["fit_card"]
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

For `search_listings`: I'll give Claude the Tool 1 spec block from this file (what it does, all three input parameters with types, return value description, failure mode) and ask it to implement the function in `tools.py` using `load_listings()` from `utils/data_loader.py`. Before running it I'll verify the generated code filters by all three parameters independently, scores by keyword overlap across title/description/style_tags/colors/brand, drops zero-score results, and handles the empty-list case. I'll test it with three queries: one that matches several items, one with a tight price filter, and one impossible query.

For `suggest_outfit`: I'll give Claude the Tool 2 spec plus the wardrobe schema structure from `data/wardrobe_schema.json`. I'll ask it to implement the function with two prompt branches (empty vs. populated wardrobe) using Groq `llama-3.3-70b-versatile`. I'll verify the code checks `wardrobe["items"]` before building the prompt and wraps the LLM call in a try/except. I'll test it with `get_example_wardrobe()` and `get_empty_wardrobe()`.

For `create_fit_card`: I'll give Claude the Tool 3 spec and ask it to implement the function with a guard on empty `outfit`, a casual-tone prompt that references item title/price/platform, and a temperature of at least 0.9. I'll verify the guard is present and run the function three times on the same input to confirm output variation.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the full Architecture diagram above plus the Planning Loop and State Management sections. I'll ask it to implement `run_agent()` in `agent.py` following the 8-step sequence exactly. Before using it I'll check that: (1) the code branches on empty `search_results` before calling `suggest_outfit`, (2) `session["selected_item"]` is set from `results[0]` not hardcoded, (3) all session keys are written in the correct order. I'll then run the two test cases already in `agent.py` (happy path and no-results path) and print the session dict to confirm state is flowing correctly.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

FitFindr takes a natural language query and orchestrates three tools in sequence: it first searches mock secondhand listings by description, size, and price (`search_listings`), then uses the top result alongside the user's wardrobe to generate a styled outfit suggestion (`suggest_outfit`), and finally produces a short, shareable caption for that outfit (`create_fit_card`). Each tool is triggered only if the previous one succeeded — if `search_listings` returns no matches, the agent stops immediately and tells the user what to adjust rather than calling the remaining tools with empty input. If `suggest_outfit` receives an empty wardrobe or `create_fit_card` receives an incomplete outfit string, each tool handles its own failure by returning a descriptive message instead of crashing.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** The agent parses the query and extracts `description="vintage graphic tee"`, `size=None` (no size mentioned), `max_price=30.0`. It calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. The function loads all 40 listings, drops any priced above $30, scores the rest by keyword overlap with "vintage graphic tee" across title/description/style_tags/colors/brand, and returns a sorted list of matches. Suppose it returns 3 results; the top result is `{"id": "lst_003", "title": "Faded Band Tee", "price": 22.0, "platform": "depop", ...}`. The agent sets `session["selected_item"] = results[0]`.

**Step 2:** The agent calls `suggest_outfit(session["selected_item"], session["wardrobe"])`. The wardrobe has items (baggy jeans, chunky sneakers, etc.), so the LLM receives a prompt listing the new item's details alongside the wardrobe pieces and is asked for specific outfit combinations. It returns something like: "Pair this faded band tee with your wide-leg jeans and platform Docs for a 90s grunge look. Tuck the front corner slightly for shape and roll the sleeves once." The agent stores this in `session["outfit_suggestion"]`.

**Step 3:** The agent calls `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. The LLM receives a prompt with the outfit description and item details (title: "Faded Band Tee", price: $22, platform: depop) and is instructed to write a 2–4 sentence casual caption. It returns something like: "thrifted this faded band tee off depop for $22 and it was literally made for wide-legs 🖤 rolled sleeves, front tuck, chunky sneakers — full look in my stories." The agent stores this in `session["fit_card"]`.

**Final output to user:** The UI populates three panels — (1) the listing summary showing title, price, condition, and platform; (2) the outfit suggestion paragraph; (3) the fit card caption ready to copy and post.

**Error path:** If step 1 returned `[]` (e.g. query was "designer ballgown size XXS under $5"), the agent sets `session["error"] = "No listings found for 'designer ballgown' in size XXS under $5. Try a broader description, remove the size filter, or raise your price limit."` and returns immediately. The UI shows the error message in panel 1 and leaves panels 2 and 3 empty.
