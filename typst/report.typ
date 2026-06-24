// DownLow report template — Phase 1 (F3) fills this in.
//
// The RenderStage serialises a list[PaperSummary] to JSON beside this template;
// the template loads it as DATA (so Typst handles escaping of arbitrary strings)
// and builds an outline + one section per paper. Compiled via the `typst` binary
// (subprocess) — deterministic, in-process, no Overleaf watcher, no sleep().

#set document(title: "Research Summaries")
#set page(numbering: "1")

= Research Summaries

// Phase 1: #let data = json("summaries.json"); #outline(); loop papers -> sections.
