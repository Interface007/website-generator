---
title: Flip-Cards
PageTitle: Sven Erik Matzen – Flip-Cards | Knowledge Quiz
Template: page-flip-cards.html.j2
---

<p class="intro-text">A spaced-repetition knowledge quiz. Pick a language, reveal each answer,
  then mark whether you knew it — cards you already know resurface less often, while new or
  uncertain ones come up more.</p>
<p style="display:flex;align-items:center;gap:12px;margin:0 0 24px;padding:10px 14px;background:var(--surface-subtle);border:1px solid var(--surface-subtle-border);border-radius:6px;font-size:.9em;line-height:1.45;color:var(--gray-medium);">
  <img class="ai-label-icon" src="img/ai-label_3x2_3_black.png" alt="EU label: fully AI-generated content" width="80" height="60" style="width:80px;height:60px;flex:0 0 auto;" />
  <span><strong>Fully AI-generated content.</strong> The flip-card prompts and answers are produced with AI assistance as part of this daily learning routine. The topics, framing, and selection are mine; the wording is generated through a structured workflow.</span>
</p>

<section class="flip-quiz">
  <div class="flip-toolbar">
    <div class="flip-langs" role="group" aria-label="Language">
      <button type="button" data-lang="de">DE</button>
      <button type="button" data-lang="en">EN</button>
    </div>
    <button type="button" id="flip-reset" class="flip-reset">⟳ <span id="flip-reset-label"></span></button>
  </div>

  <div id="flip-message" class="flip-message flip-hidden"></div>

  <div id="flip-card" class="flip-card flip-hidden" aria-live="polite">
    <div class="flip-card__inner">
      <div class="flip-card__face flip-card__face--front">
        <span class="flip-card__tag" id="flip-tag-q"></span>
        <p class="flip-card__text" id="flip-question"></p>
      </div>
      <div class="flip-card__face flip-card__face--back">
        <span class="flip-card__tag" id="flip-tag-a"></span>
        <p class="flip-card__text" id="flip-answer"></p>
      </div>
    </div>
  </div>

  <div id="flip-actions" class="flip-actions flip-hidden">
    <button type="button" id="flip-reveal" class="flip-btn flip-btn--primary"></button>
    <div id="flip-decision" class="flip-decision flip-hidden">
      <button type="button" id="flip-dont-know" class="flip-btn flip-btn--danger"></button>
      <button type="button" id="flip-know" class="flip-btn flip-btn--success"></button>
    </div>
    <p id="flip-hint" class="flip-hint"></p>
    <p id="flip-status" class="flip-status"></p>
  </div>
</section>
