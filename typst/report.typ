// DownLow report template (F3) -- a DETERMINISTIC, data-driven document.
//
// The RENDER stage (adapters/render/typst_renderer.py) serialises a ReportData
// (a ReportMeta + an ordered list[PaperSummary]) to `summaries.json` beside this
// template, then compiles `typst compile report.typ out.pdf`. The template loads
// that file as DATA via `json(...)`, so Typst escapes arbitrary summary strings --
// the LLM never emits markup (the old LaTeXConverter fragility is gone).
//
// Identical input => byte-stable PDF: no timestamps, no randomness, no system
// fonts assumed beyond Typst's bundled defaults. Restyle freely; bump
// REPORT_TEMPLATE_VERSION in core/stages/render.py whenever this changes.

#let data = json("summaries.json")
#let meta = data.meta
#let summaries = data.summaries

#set document(title: meta.title)
#set page(numbering: "1")
#set par(justify: true)
#set text(size: 10.5pt)
#set heading(numbering: "1.1")

// --- Title page (no contents heading is numbered) --------------------------- //
#[
  #set align(center + horizon)
  #text(size: 22pt, weight: "bold")[#meta.title]
  #v(1em)
  #text(size: 11pt, fill: luma(90))[
    #summaries.len() #if summaries.len() == 1 [paper] else [papers]
  ]
]

#pagebreak()

// --- Contents --------------------------------------------------------------- //
#outline(title: "Contents", depth: 1)

// --- Small helpers ---------------------------------------------------------- //

// A bulleted list of plain strings; renders nothing when the list is empty.
#let string-list(items) = {
  if items != none and items.len() > 0 {
    list(..items.map(it => [#it]))
  }
}

// A prose sub-section: a level-2 heading + a paragraph, only when non-empty.
#let prose-section(name, body) = {
  if body != none and body.trim() != "" {
    heading(level: 2)[#name]
    par[#body]
  }
}

// A list sub-section: a level-2 heading + a bulleted list, only when non-empty.
#let list-section(name, items) = {
  if items != none and items.len() > 0 {
    heading(level: 2)[#name]
    string-list(items)
  }
}

// Key findings: each is a statement with optional evidence detail beneath it.
#let findings-section(findings) = {
  if findings != none and findings.len() > 0 {
    heading(level: 2)[Key Findings]
    for f in findings {
      block(below: 0.8em)[
        - #f.statement
        #if "evidence" in f and f.evidence != none and f.evidence.trim() != "" {
          [ #h(1em) #text(size: 9pt, fill: luma(90), style: "italic")[Evidence: #f.evidence] ]
        }
      ]
    }
  }
}

// --- One section per paper, in document order ------------------------------- //
#for (i, paper) in summaries.enumerate() {
  if i > 0 { pagebreak() }
  heading(level: 1)[#paper.title]

  prose-section("Summary", paper.overall_summary)
  findings-section(paper.key_findings)
  list-section("Contributions", paper.contributions)
  prose-section("Methods", paper.methods)
  list-section("Gaps & Limitations", paper.gaps_and_limitations)
  prose-section("Relevance", paper.relevance_to_profile)
}
