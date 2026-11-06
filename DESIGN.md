# The Standard Edition design guide

The brand and design rules for The Standard Edition. Read this before changing anything a reader sees: the site, feeds, social previews, docs or any new surface.

If a choice isn't covered here, take the plainer option. If a rule needs to change, change it here first, in the same pull request.

**Status:** version 1, 2026-11-05. The direction is chosen but not built. `web/` still has the previous design. See [Moving the site over](#14-moving-the-site-over).

The approved visual reference is the "The blend" board on the [brand canvas](https://claude.ai/artifact/E8eY8W89an8E5ckUVnhM72) (private to the owner). Where this file and the canvas differ, this file wins.

**Related files:**

- [`editorial/style_guide.md`](editorial/style_guide.md) sets how stories are written. This file sets how the site's own words and visuals work.
- [`docs/roadmap.md`](docs/roadmap.md) tracks what's planned.
- [`GLOSSARY.md`](GLOSSARY.md) defines project terms.

---

## 1. Brand foundation

### What it is

The Standard Edition is a free, once-a-day news edition that shows what happened, who covered it and who didn't.

### The thesis

Gather enough reporting from across the political spectrum, and what the sources have in common points toward what's true. Put public records beside the reporting, show the gaps, and let the reader do the rest.

Agreement only counts when sources are independent, and every outlet can miss the same thing. The site says so plainly (roadmap T7).

### Positioning

| | |
| --- | --- |
| **For** | People who want to stay informed without being worked up or steered |
| **Instead of** | Endless feeds, a single trusted outlet, or giving up on the news |
| **Category** | A public daily edition, not a news app and not an aggregator feed |
| **What only we do** | Every ranking rule, source label and dollar is public, and readers can change the rules |
| **What readers get** | A short, calm read, a clear view of who said what, and their own conclusion |

**We say no to:** ads, accounts, tracking, engagement metrics, infinite scroll, breaking-news alerts, sports for now, and telling readers what to think.

### Principles

1. **Show, don't rule.** The site shows evidence. It doesn't decide for the reader. This is why we never highlight or mark words in outlets' text.
2. **The gap is the signal.** Who didn't cover a story is the most distinctive thing on the page, and it gets the only color.
3. **Calm is a feature.** Nothing moves, flashes or competes for attention. The edition has an end.
4. **Classic in the masthead, open everywhere else.** The newspaper tradition earns trust at the top. Below it, the page is spacious and speaks plainly.
5. **Nothing hidden.** Any claim the site makes links to its proof.
6. **Built for every reader.** Each decision has to survive other languages, slow connections, screen readers and blocked domains.

---

## 2. Messaging and voice

### Message levels

| Level | Use | Words |
| --- | --- | --- |
| One line | Social bios, search results | The day's news, once a day. Who covered it, who didn't, and every rule in public. |
| Short | About page opening, link previews | The Standard Edition reads outlets across the political spectrum and public records, then publishes one plain edition a day. It's free, with no ads, accounts or tracking. The rules are public, and you can change them. |
| Long | About page | The thesis, how a story gets chosen, who runs it, how it's paid for, and the FAQ |

**Closing line:** "That's the edition. The rest is up to you." This ends every Today page. It's the brand's main line, because it states the promise: we stop, and your thinking starts.

### Voice

| We are | Which means | We aren't |
| --- | --- | --- |
| **Plain** | Everyday words and short sentences | Dumbed down or chatty |
| **Calm** | Facts without urgency | Dull or detached |
| **Open** | We show our work and admit limits | Defensive or self-congratulating |
| **Respectful** | We trust readers to decide | Preachy or instructive |

**Tone shifts by context.** Stories follow the editorial style guide. Interface text is friendly and direct. Errors state what happened and what to do next. The About page can be warmer and more personal than anywhere else.

### Sentences that sound right

- Five stories today. Left, center and right covered three of them.
- Among the outlets we read, no left outlet ran this.
- A gap isn't proof of anything. It's worth a second look.
- We couldn't read right outlets today, so we can't say whether they covered this.
- Nothing matches your settings. Try needing less agreement, or turn on more categories.

### Rules for what we claim

- **Coverage gaps are facts about our list.** Say "among the outlets we read." Never say "ignored," "buried," "skipped" or "refused," which all imply a motive.
- **Don't claim to have the truth.** "Get closer to the truth" is fine for the mission. "Here's the truth" or "unbiased" isn't, and neither is "fact-checked" for a whole story.
- **Don't say "nonprofit" or "not a company"** until the legal form is settled and shown on the About page. The `.org` address doesn't prove it.
- **Be upfront about AI.** Say a model writes the summaries wherever a reader would want to know (decision D7).
- **Keep our own language.** Don't use "Keep thinking," which is Anthropic's line. Avoid "You decide" and "Fair and balanced," which belong to Fox News. Don't riff on "All the News That's Fit to Print."

### Names

- **The name:** The Standard Edition. Use "the Standard Edition" mid-sentence, with a lowercase "the."
- **The address:** standardedition.org, always lowercase.
- **Sections:** Today, All stories, Outlets, Research, How it works, Your feed, About.
- **Terms:** use "outlets," "stories," "edition" and "government record," as defined in the glossary. Use sentence case everywhere.

---

## 3. Logo

### The mark

The logo is the name set in an open serif, with an Old English capital S as its one ornate letter.

```
The 𝕾tandard Edition
standardedition.org
```

- **Words:** Literata Regular, tracking −0.015em.
- **The S:** blackletter, 1.42 times the size of the words, on the same baseline.
- **Address line:** Literata Regular, about 24% of the word size, centered beneath.

### Versions

| Version | Use |
| --- | --- |
| **Full** (name and address) | Desktop masthead, About page, social images |
| **Name only** | Phone masthead, feeds, narrow spaces |
| **Initial** (S alone) | Favicon, app icon, social avatar |

### Rules

- **Clear space:** at least the height of the "t" in "tandard" on every side.
- **Minimum size:** name 150px wide on screen, address line shown only above 320px wide, initial 16px.
- **Colors:** `--ink` on `--desk`, or reversed. One color only.
- **The logo stays in Latin letters in every language.** Translate the tagline or date around it, never the logo.

**Don't:** stretch it, outline it, add effects, set the whole name in blackletter, use the blackletter for anything else, or put the logo on a photograph.

### Before launch

The current S comes from a free font called Manufacturing Consent, as a stand-in. Before launch, the S needs to be drawn by hand and saved as SVG:

- Its shape resembles the New York Times nameplate, and ours should be distinct.
- An SVG loads no extra font and looks the same everywhere.
- The font's name would look odd in a project promising that nothing's hidden.

---

## 4. Color

The palette is ink on white, plus one warm color for gaps. There's no brand accent: the logo, type and scale carry the identity.

### Tokens

Keep the existing names from `web/style.css` where they still apply, so the change stays small. `--control` is new. `--accent`, `--on-accent`, `--well`, `--mast`, `--shadow` and `--inset` are retired: links and buttons use `--ink` and `--desk`, the masthead uses the page colors, and nothing has a shadow. Replace each use of a retired token before removing it.

| Token | Role | Light | Dark |
| --- | --- | --- | --- |
| `--desk` | Page background | `#ffffff` | `#141518` |
| `--sheet` | Tinted bands and panels | `#f3f3f0` | `#1e1f23` |
| `--ink` | Text, ticks, buttons, rules | `#17181c` | `#ecebe6` |
| `--muted` | Secondary text | `#4c4d53` | `#b0afa9` |
| `--line` | Dividers (decorative only) | `#dedcd6` | `#35363b` |
| `--control` | Borders of inputs and buttons | `#8a8b91` | `#7d7e84` |
| `--gap` | Coverage gap stripes | `#b57a00` | `#e9b23a` |
| `--c-record` | Government record chart segment | `#2f6b57` | `#8fcdb4` |
| `--up` | Market value rose | `#2f6b57` | `#8fcdb4` |
| `--down` | Market value fell | `#a13a2c` | `#e8a092` |

### Measured contrast

| Pair | Light | Dark |
| --- | --- | --- |
| Ink on desk | 17.7:1 | 15.3:1 |
| Ink on sheet | 16.0:1 | 13.8:1 |
| Muted on desk | 8.4:1 | 8.3:1 |
| Muted on sheet | 7.6:1 | 7.5:1 |
| Gap on desk | 3.7:1 | 9.5:1 |
| Gap on sheet | 3.3:1 | 8.5:1 |
| Control on desk | 3.4:1 | 4.5:1 |

`--gap` and `--control` are for shapes and borders, never text. `--line` is too faint to be a control's only outline.

### Use

- **About 95% ink and white.** `--sheet` appears for one band per page, or to group a settings panel.
- **Amber means one thing:** a side of the spectrum didn't run the story. Never use it for warnings, links, hover states or decoration.
- **Links are ink with an underline.** Hover makes the underline darker, not a new color.
- **Flag colors** appear only inside the location control.

### Score chart

Four segments, told apart by lightness and fill as well as hue. Each one measures at least 3:1 against the page.

| Segment | Light | Dark |
| --- | --- | --- |
| Breadth | `--ink` | `--ink` |
| Government record | `--c-record` | `--c-record` |
| Coverage | `#8a8b91` | `#7d7e84` |
| Diversity | Empty, with a 1px `--control` outline | Same |

---

## 5. Typography

### Families

| Family | Role |
| --- | --- |
| **Literata** | Logo words, headlines, the opening sentence, story text |
| **Source Sans 3** | Navigation, labels, notes, controls, tables |
| **System mono** (`ui-monospace`) | Code and feed addresses only |

Both main families cover Latin, Cyrillic, Greek and Vietnamese. Retire Schibsted Grotesk, Source Serif 4 and Geist Mono from the page.

### Scale

| Style | Family | Size | Weight | Line height | Tracking |
| --- | --- | --- | --- | --- | --- |
| Logo, desktop | Literata | 76px | 400 | 1.1 | −0.015em |
| Opening sentence | Literata | `clamp(28px, 3.3vw, 44px)` | 400 | 1.22 | −0.015em |
| Lead headline | Literata | `clamp(28px, 3vw, 40px)` | 500 | 1.16 | −0.012em |
| Page title | Literata | `clamp(30px, 3.4vw, 44px)` | 500 | 1.18 | −0.012em |
| Section heading | Literata | 28px | 500 | 1.25 | −0.01em |
| Column heading | Literata | 21px | 500 | 1.3 | 0 |
| Story headline | Literata | 19 to 20px | 500 | 1.3 | 0 |
| Story text, lead | Literata | 19px | 400 | 1.6 | 0 |
| Story text, phone | Literata | 17px | 400 | 1.55 | 0 |
| Interface | Source Sans 3 | 16px | 400, 600 | 1.5 | 0 |
| Notes, labels | Source Sans 3 | 15px | 400 | 1.5 | 0 |
| Notices | Source Sans 3 | 14px | 400 | 1.5 | 0 |

### Rules

- **Nothing below 14px.**
- **Keep reading text under 34em wide.** That's about 70 characters.
- **Use sentence case.** No all-caps labels and no spaced-out letters.
- **Literata weights are 400 and 500 only.** Heavy headlines read as shouting.
- **No italics for emphasis.** Use them only for titles of works.
- **Left-align reading text.** Center only the logo, the navigation and the closing line.
- **Numbers stay with their words.** Don't turn counts into large stat graphics.

### Other scripts

Keep the same roles, and load a script's font only when that language is chosen.

| Script | Serif role | Sans role |
| --- | --- | --- |
| Latin, Cyrillic, Greek, Vietnamese | Literata | Source Sans 3 |
| Arabic | Noto Naskh Arabic | Noto Sans Arabic |
| Hebrew | Noto Serif Hebrew | Noto Sans Hebrew |
| Devanagari | Noto Serif Devanagari | Noto Sans Devanagari |
| Chinese | Noto Serif SC | Noto Sans SC |

CJK fonts are large, so test them on slow connections. Native system fonts are an acceptable fallback, and the page must be readable before any web font arrives (`font-display: swap`).

---

## 6. Layout

### Grid

| | |
| --- | --- |
| Page width | 1180px maximum, centered |
| Side margin | 32px on desktop, 16px on phone |
| Main columns | Lead story takes 3 parts, Also today takes 2, with a 48px gap |
| Base spacing | Multiples of 4px: 8, 12, 16, 24, 32, 48, 64 |

Below 880px, everything falls into one column, with the lead story first. The DOM order must match the visual order at all sizes.

### Today page

```
 Sample notice (only on sample editions)
 ──────────────────────────────────────────────
 Wednesday, November 4, 2026       [US] [English]

          The 𝕾tandard Edition
          standardedition.org
 ──────────────────────────────────────────────
  Today  All stories  Outlets  Research  How it works  Your feed  About
 ──────────────────────────────────────────────

 Five stories today. Left, center and right
 covered three of them.

 Lead headline                   Also today
 ▮▮ ▮▮ ▮▮▮                       ─────────────
 Left 2  Center 2  Right 3       Story
                                 ▮ ▮▮ ▮
 • Bullets                       ─────────────
 What's next                     Story
 See all outlets                 ▨ ▮ ▮
                                 Left: no outlet ran this

 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
 ░ Only one side covered                      ░
 ░ Story              Story                   ░
 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

        That's the edition.
        The rest is up to you.
        See all 17 stories
```

**The order of importance:** logo, opening sentence, lead headline, coverage scale, everything else.

### Other pages

Every tab keeps the same masthead, then a page title with a short introduction, then its content in one column up to 44em wide. Tools, tables and charts may use the full 1180px.

### No cards by default

Separate stories with space and a hairline. Don't wrap each one in a box. Use `--sheet` only when things truly form a group, like the one-sided band or a settings panel.

---

## 7. Components

All new components use these tokens. Radius is 0, apart from pill controls at full radius, so anything rounded reads as something to press.

### Masthead

The date sits top left, and the location and language controls top right, then the logo and navigation. It doesn't stick to the top of the screen, so the page stays open while reading.

### Navigation

- Plain text between two 1px `--ink` rules. The current tab is 600 weight.
- On a phone, one row that scrolls sideways if needed, with no hamburger menu. Sections should be seen.
- Tap area at least 44px tall.

### Location and language controls (planned)

- **Location:** flag and country code, like "US." Opens a list of editions.
- **Language:** the language's name in itself (English, Español, العربية). Never a flag.
- They're separate settings. Both are pills with a `--control` border, 44px tall. They merge into one pill on a phone ("US, EN"), which opens both lists.
- List only what exists, and mark anything else as planned. Flags are drawn as small SVGs, because Windows doesn't show flag emoji.
- Both live in the browser and the feed address, like every other setting. Never detect location from a reader's IP address.

### Opening sentence

One to three plain sentences that sum up the day from real data: how many stories, how many had all sides, and what's notable. This replaces the old "Five stories today" title and explanation. It's generated from the edition, and must stay true for every reader's settings.

### Lead story

Headline, full-width coverage scale with counts, bullets, "What's next" when there is one, then a link to the outlets and their headlines.

The headlines appear plain and unmarked. No highlighting, underlining or scoring of outlets' words, here or anywhere.

### Story row

Headline, compact scale, then one note if needed ("Backed by a government record," or the gap sentence). No topic label unless it's the page's way of grouping.

### Coverage scale

The scale is the brand's signature, and appears on every story. It has three equal segments in fixed order: left, center, right.

| State | Look | Meaning |
| --- | --- | --- |
| **Covered** | One solid `--ink` tick per outlet | That many outlets ran it |
| **Gap** | Diagonal `--gap` stripes, 3px on and 3px off, at 135° | We read that side, and nothing ran |
| **Unread** | Empty, with a 1px dashed `--control` outline | That side's feeds failed, so we don't know |

| Size | Height | Labels |
| --- | --- | --- |
| Lead | 10px | Count below each segment ("Left: 2") |
| Compact | 8px | None, but a note appears when a side is missing |

**Rules:**

- Segments are always equal width, whatever the outlet count.
- Ticks fill their segment, with a 2px gap between them.
- A gap must never rely on color alone. The stripes are the pattern, and the note says it in words.
- The whole scale has one screen-reader label, like "Left 2, center 2, right 3."
- An unread side is never shown as a gap. Don't claim silence when we simply couldn't look.
- The order stays left, center, right in every language, including right-to-left ones.

### One-sided band

A full-width `--sheet` band after the main stories, with a heading, the line "A gap isn't proof of anything. It's worth a second look," and two columns of stories. Each story states the fact in the established wording.

### Closing

The closing line, centered, in the opening-sentence style, then a link to all stories. Nothing follows it except the footer. This is the anti-infinite-scroll moment, and it should feel finished.

### Buttons and links

| Type | Look | Use |
| --- | --- | --- |
| Primary | `--ink` background, `--desk` text, pill, 44px tall | The one main action on a screen, like "Look up" |
| Secondary | `--control` border, pill, 44px tall | Everything else, like "Copy" |
| Link | Underlined text | Going somewhere |

Button labels say what happens ("Copy link," then "Copied"). Links never end in an arrow.

### Forms and settings

Labels sit above fields, always visible, and placeholder text is only an example. Inputs have a `--control` border and a 2px `--ink` focus outline. Sliders show their value in words beside them. Settings save at once, so there's no Save button.

### Tables

Hairline rows, no vertical rules, left-aligned text and right-aligned numbers. Wide tables scroll inside their own box on a phone.

### Charts

Flat segments with direct labels where possible. Follow the score chart colors above. The threshold is one thin `--ink` line. Every chart has a text version.

### Market closes

A quiet row of yesterday's closes under the navigation, in Source Sans 3 at 15px. It stays still, replacing the current scrolling ticker, which conflicts with calm. It scrolls sideways on a phone only if the reader swipes. Each value links to its source, and rises or falls are shown with words or signs as well as color.

### Notices

- **Sample edition:** a thin `--sheet` bar at the very top, in 14px text. Required on all invented content.
- **Failed feeds or corrections:** a plain note at the top of Today, stating what happened and linking to the details.

### Empty and error states

Say what happened and what to do next, with no apology, illustration or joke.

---

## 8. Imagery and icons

**No photos in the edition.** RSS gives us no rights to them, and a photo chosen by us would frame the story. Type and the scale do this job.

If an image is ever needed outside the edition, like a social preview, use the logo on `--desk` or `--ink` with one line of text. No stock photos, AI images, illustrations of people, or gradients.

**Icons:** prefer words. Where an icon is needed, use a simple 1.5px outline at 16 or 20px, and add a text label unless its meaning is universal. No emoji in the interface.

**Social preview:** a 1200×630 image with the logo centered on white, with a hairline rule and the day's opening sentence beneath, generated with each edition.

---

## 9. Motion

The page holds still. Motion only responds to what the reader does.

- **Allowed:** opening a section, switching a tab, a "Copied" confirmation, and focus and hover changes. 120 to 200ms, ease-out.
- **Not allowed:** autoplay, loading animations on arrival, parallax, anything that loops, or elements fading in as you scroll.
- With `prefers-reduced-motion`, remove all transitions.

---

## 10. Accessibility

Target WCAG 2.2 AA, and treat it as a minimum.

- Text contrast of at least 4.5:1, and 3:1 for meaningful shapes and control borders.
- Every action works by keyboard, with a visible 2px focus outline.
- Tap targets of at least 44×44px.
- Color is never the only signal.
- Use real headings, landmarks, lists, buttons and labels, in logical order.
- The page works at 200% zoom and 320px wide with no sideways page scrolling, except inside tables.
- Dark mode is the reader's choice, and meets the same rules.
- Set `lang` and `dir` on the page, and on any passage in another language.

---

## 11. Languages and regions

Planned in roadmap items I1 to I6. New work should stay ready for them.

- **Keep all interface text in one place,** never hard-coded inside layouts, once I2 starts.
- **Use logical CSS** (`margin-inline-start`, not `margin-left`), so right-to-left layouts mirror automatically.
- **Allow for longer text.** German and Spanish can run 30% longer. Controls must wrap rather than clip.
- **Format dates and numbers by locale,** using the browser's `Intl` tools.
- **In right-to-left languages:** text and layout mirror, but the logo and the scale's left-to-center-right order don't.
- **Language and location stay separate.** Someone in Texas can read the US edition in Spanish.
- **Each country's edition gets its own groups.** Left, center and right aren't universal, and censored countries need a different approach (I6). The scale's three-segment form may hold different labels, so don't hard-code those labels into its design.
- **Stay light.** Censored and low-bandwidth readers matter. Target under 200KB of page weight before fonts, working without web fonts, and core reading without JavaScript where possible.

---

## 12. Page guidance

| Tab | Job | Notes |
| --- | --- | --- |
| **Today** | Read the day, then stop | As specified above |
| **All stories** | See everything, by topic | Story rows under topic headings |
| **Outlets** | Compare what each outlet ran | Table first, plain definitions |
| **Research** | Check a claim or record | Search leads the page. The site never says whether a claim is true |
| **How it works** | Prove the method | Plain steps, then the formula, then live numbers |
| **Your feed** | Own the rules | Settings first. Every change shows its effect |
| **About** (planned) | Explain why, and who | See below |

### About page (roadmap L11)

1. **Mission:** one short paragraph.
2. **The thesis:** what commonalities across sources can show, and where that falls short.
3. **What we believe:** the principles from the README.
4. **Who runs it and who pays:** with a link to the ledger.
5. **FAQ:**
   - Is this written by AI?
   - Who pays for it?
   - Are you biased?
   - Why is an outlet labeled the way it is?
   - Why was a story left out?
   - Does this tell me what's true?
   - How do I challenge a decision?
6. **Contact:** corrections and challenges.

Every answer should link to its evidence: code, ledger, source list or correction log.

---

## 13. Never do this

- Highlight, mark or grade words in outlets' text.
- Use amber for anything but a coverage gap.
- Treat a side we couldn't read as a side that didn't cover a story.
- Imply motive for a gap.
- Use photos, stock images or AI images in the edition.
- Add ads, pop-ups, sign-up prompts, streaks, notification requests or share counts.
- Rank or style anything by clicks or engagement.
- Add infinite scroll, or anything after the closing line except the footer.
- Use "breaking," urgency colors or countdowns.
- Set the whole logo, or anything else, in blackletter.
- Use flags for languages.
- Add new typefaces or colors without changing this file.
- Use the generated-page habits that make sites look alike: all-caps labels, gradient washes, a card around everything, and arrows after link text.

---

## 14. Moving the site over

Do these in order, in small changes. Nothing here changes the rubric or the data. The tests in `tests/page_smoke.cjs` must keep passing.

1. **Tokens and type:** replace the color values and fonts in `web/style.css`, and update the Google Fonts link in `web/index.html`.
2. **Masthead:** new logo, centered layout and About in the navigation. Update the site's name to The Standard Edition, along with feed titles and page titles.
3. **Coverage scale:** ticks and stripes as specified, keeping the existing three states and screen-reader labels.
4. **Today page:** the opening sentence, the lead and list layout, the one-sided band and the closing.
5. **Other tabs:** apply the type and spacing, then remove the old card styles.
6. **Market closes:** replace the scrolling ticker.
7. **About page:** build it once its words are written (L11).
8. **Before launch:** a hand-drawn S, the favicon and the social preview (L10).

The location and language controls wait for their roadmap items. Don't ship controls that do nothing.

### Review checklist

Before merging any change a reader can see:

- [ ] It works from 320px to wide desktop, in light and dark.
- [ ] It works by keyboard and with a screen reader.
- [ ] The only color added is for a coverage gap.
- [ ] Words follow section 2, and any claim links to proof.
- [ ] Nothing moves unless the reader caused it.
- [ ] It would still work in another language.

---

## 15. Decision log

| Date | Decision | Why |
| --- | --- | --- |
| 2026-11-05 | Blend of the Nameplate and Open Page directions | The classic masthead earns trust, and the open page keeps it personable |
| 2026-11-05 | Logo: Old English S with open words | Tradition and modern openness in one mark |
| 2026-11-05 | Name: The Standard Edition, with standardedition.org beneath | A publication's name, and the .org stays visible |
| 2026-11-05 | No highlighting of words | The site shows evidence and doesn't judge language for the reader |
| 2026-11-05 | No photos | No rights from RSS, and a chosen photo frames a story |
| 2026-11-05 | Amber only for gaps | Keeps the one loud thing meaningful |
| 2026-11-05 | Closing line: "The rest is up to you" | The brand's own way of asking readers to keep thinking for themselves |

### What we took from the references

| Reference | Kept | Left behind |
| --- | --- | --- |
| The New York Times | The authority of an Old English masthead | The full blackletter logo and its slogan |
| Anthropic | Openness, plain warmth, a large sentence as the opening | Its colors, fonts and "Keep thinking" |
| Bloomberg Vision Pro concept | A clear masthead over organized columns | Photo-led stories |
| Fidabio news section | A strong statement beside a simple story list | Gradient button and repeated boxes |
| Dstudio news section | Serif headlines with rich column rhythm | Highlighted phrases and photos |
| Scott Bair's playbook | Brand as a system: positioning, messaging, identity and rules | Its focus on sales and premium pricing |
