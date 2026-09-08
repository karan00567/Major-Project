<script setup>
// Summary-generation model — facebook/bart-base, encoder–decoder.
//
// BART is the only one of the three whose checkpoint is not in this repo, so
// the figures here are the published `facebook/bart-base` configuration:
// 6 encoder + 6 decoder layers, d_model 768, 12 heads each side,
// ffn_dim 3072, vocab 50,265, max_position_embeddings 1024, ~139M parameters.
// The two-lane drawing is the point — an encoder-only model cannot generate,
// and that is the difference between this model and the other two.
import ArchBox from './ArchBox.vue'
import ArchArrow from './ArchArrow.vue'
</script>

<template>
  <svg viewBox="0 0 1000 458" width="100%" role="img"
       aria-label="BART-base architecture: a six-layer bidirectional encoder and a
                   six-layer autoregressive decoder joined by cross-attention over
                   the encoder memory.">
    <rect x="86" y="46" width="900" height="122" rx="12" class="arch-group" />
    <text x="18" y="96" class="arch-lane">encoder</text>
    <rect x="86" y="316" width="900" height="122" rx="12" class="arch-group" />
    <text x="18" y="366" class="arch-lane">decoder</text>

    <ArchBox :x="102" :y="60" :w="196" :h="88" title="Paper text from cache"
             :lines="['full text, not the abstract', '≤ 1,024 BPE tokens~',
                      'vocab 50,265']" tone="accent" />
    <ArchArrow :x1="298" :y1="104" :x2="326" :y2="104" />

    <ArchBox :x="326" :y="60" :w="160" :h="88" title="Embeddings"
             :lines="['token + learned position', 'no segment ids', '→ 768-d~']" />
    <ArchArrow :x1="486" :y1="104" :x2="514" :y2="104" />

    <ArchBox :x="514" :y="60" :w="206" :h="88" title="Encoder block"
             :lines="['bidirectional self-attention', '12 heads · FFN 3,072', 'GELU']"
             badge="× 6" stack />

    <ArchBox :x="768" :y="60" :w="204" :h="88" title="Serves two agents"
             :lines="['Extractor: paper → summary', 'Writer: summaries → section',
                      'same weights, different prompt']" tone="muted" />

    <!-- The encoder's output, held once and read by every decoder layer. -->
    <ArchArrow :x1="617" :y1="148" :x2="617" :y2="210" kind="v" />
    <ArchBox :x="512" :y="210" :w="210" :h="62" title="Encoder memory"
             :lines="['one 768-d vector per token~']" tone="accent" />
    <ArchArrow :x1="617" :y1="272" :x2="617" :y2="328" kind="v" dashed />
    <text x="634" y="304" class="arch-cap">cross-attention, every decoder layer</text>

    <ArchBox :x="102" :y="330" :w="196" :h="88" title="Summary so far"
             :lines="['shifted right~', 'teacher forcing in training',
                      'beam search at inference']" />
    <ArchArrow :x1="298" :y1="374" :x2="326" :y2="374" />

    <ArchBox :x="326" :y="330" :w="160" :h="88" title="Embeddings"
             :lines="['token + learned position', '→ 768-d~']" />
    <ArchArrow :x1="486" :y1="374" :x2="514" :y2="374" />

    <ArchBox :x="514" :y="330" :w="206" :h="88" title="Decoder block"
             :lines="['masked self-attention', 'cross-attention → memory',
                      '12 heads · FFN 3,072']" badge="× 6" stack />
    <ArchArrow :x1="720" :y1="374" :x2="748" :y2="374" />

    <ArchBox :x="748" :y="330" :w="224" :h="88" title="LM head"
             :lines="['tied to the token embedding', '768 → 50,265', 'generated summary']"
             tone="good" />

  </svg>
</template>
