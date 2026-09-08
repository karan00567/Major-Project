<script setup>
// Cross-encoder ranker — BertForSequenceClassification, 6 layers.
//
// Every figure on this diagram is read from data/models/reranker-mixed/config.json:
// hidden_size 384, num_hidden_layers 6, num_attention_heads 12,
// intermediate_size 1536, vocab_size 30522, max_position_embeddings 512,
// type_vocab_size 2, and a single output label — a relevance logit, not a class.
import ArchBox from './ArchBox.vue'
import ArchArrow from './ArchArrow.vue'
</script>

<template>
  <svg viewBox="0 0 1000 384" width="100%" role="img"
       aria-label="Cross-encoder ranker architecture: a joint query-and-abstract
                   sequence through six transformer encoder layers to a single
                   relevance logit.">
    <ArchBox :x="14" :y="60" :w="222" :h="88" title="Cross-encoder input"
             :lines="['[CLS] query [SEP] abstract [SEP]~', '≤ 512 WordPiece tokens',
                      'one joint sequence']" tone="accent" />
    <ArchArrow :x1="236" :y1="104" :x2="266" :y2="104" />

    <ArchBox :x="266" :y="60" :w="156" :h="88" title="Embeddings"
             :lines="['token 30,522 · position 512', 'segment 2', '→ 384-d~']" />
    <ArchArrow :x1="422" :y1="104" :x2="452" :y2="104" />

    <ArchBox :x="452" :y="60" :w="196" :h="88" title="Transformer encoder"
             :lines="['12 heads · d_k 32', 'FFN 384 → 1536 → 384', 'GELU']"
             badge="× 6" stack />
    <ArchArrow :x1="648" :y1="104" :x2="678" :y2="104" />

    <ArchBox :x="678" :y="60" :w="140" :h="88" title="[CLS] pooling"
             :lines="['first token', '384-d vector~']" />
    <ArchArrow :x1="818" :y1="104" :x2="848" :y2="104" />

    <ArchBox :x="848" :y="60" :w="138" :h="88" title="Linear 384 → 1"
             :lines="['relevance logit', 'sorts the pool', '1 in 10 retained']"
             tone="good" />

    <!-- Leader from the stacked encoder into its own expansion below. -->
    <path d="M 550 148 V 176 H 300 V 214" class="arch-line" stroke-dasharray="5 4"
          fill="none" />
    <path d="M 300 214 L 294 202 L 306 202 Z" class="arch-arrowhead" />

    <rect x="96" y="216" width="808" height="146" rx="12" class="arch-group" />
    <text x="112" y="238" class="arch-lane">one encoder layer</text>

    <ArchBox :x="118" :y="252" :w="182" :h="74" title="Multi-head attention"
             :lines="['12 heads, 32 dims each', 'query ↔ abstract']" tone="muted" />
    <ArchArrow :x1="300" :y1="289" :x2="326" :y2="289" />
    <ArchBox :x="326" :y="252" :w="146" :h="74" title="Add &amp; LayerNorm"
             :lines="['residual']" tone="muted" />
    <ArchArrow :x1="472" :y1="289" :x2="498" :y2="289" />
    <ArchBox :x="498" :y="252" :w="182" :h="74" title="Feed-forward"
             :lines="['384 → 1536 → 384', 'GELU']" tone="muted" />
    <ArchArrow :x1="680" :y1="289" :x2="706" :y2="289" />
    <ArchBox :x="706" :y="252" :w="146" :h="74" title="Add &amp; LayerNorm"
             :lines="['residual']" tone="muted" />

    <!-- Residual paths, drawn under the row so they never cross a label. -->
    <path d="M 118 336 V 348 H 399 V 330" class="arch-line-soft" fill="none" />
    <path d="M 498 336 V 348 H 779 V 330" class="arch-line-soft" fill="none" />
    <text x="399" y="360" text-anchor="middle" class="arch-cap">residual</text>
    <text x="779" y="360" text-anchor="middle" class="arch-cap">residual</text>

  </svg>
</template>
