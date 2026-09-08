<script setup>
// Claim verifier — DebertaV2ForSequenceClassification, 6 layers.
//
// Read from data/models/verifier-scifact/config.json: hidden_size 768,
// num_hidden_layers 6, num_attention_heads 12, intermediate_size 3072,
// vocab_size 128100, relative_attention true, pos_att_type ["p2c","c2p"],
// position_buckets 256, position_biased_input false (so no absolute position
// is added to the input embedding — the thing that makes DeBERTa DeBERTa),
// type_vocab_size 0, and id2label {SUPPORT, CONTRADICT, NEI}.
import ArchBox from './ArchBox.vue'
import ArchArrow from './ArchArrow.vue'
</script>

<template>
  <svg viewBox="0 0 1000 486" width="100%" role="img"
       aria-label="DeBERTa-v3-small verifier architecture: a claim and its evidence
                   span through six disentangled-attention layers to a three-way
                   verdict and a 0.7 support threshold.">
    <ArchBox :x="14" :y="56" :w="230" :h="88" title="Claim + evidence"
             :lines="['[CLS] claim [SEP] span [SEP]~', '≤ 256 SentencePiece tokens',
                      'vocab 128,100']" tone="accent" />
    <ArchArrow :x1="244" :y1="100" :x2="270" :y2="100" />

    <ArchBox :x="270" :y="56" :w="192" :h="88" title="Disentangled input"
             :lines="['content embedding 768-d', 'relative position, 256 buckets',
                      'no absolute position added']" />
    <ArchArrow :x1="462" :y1="100" :x2="488" :y2="100" />

    <ArchBox :x="488" :y="56" :w="196" :h="88" title="DeBERTa-v3 encoder"
             :lines="['12 heads · FFN 3,072', 'content→position and', 'position→content']"
             badge="× 6" stack />
    <ArchArrow :x1="684" :y1="100" :x2="710" :y2="100" />

    <ArchBox :x="710" :y="56" :w="122" :h="88" title="Pooler"
             :lines="['768 · GELU', 'dropout 0']" />
    <ArchArrow :x1="832" :y1="100" :x2="858" :y2="100" />

    <ArchBox :x="858" :y="56" :w="128" :h="88" title="Linear → 3"
             :lines="['softmax']" tone="accent" />

    <!-- One head, three classes: fan the logits out to the verdicts. -->
    <path d="M 922 144 V 186 H 234 M 430 186 V 214 M 626 186 V 214 M 234 186 V 214"
          class="arch-line" fill="none" />
    <path d="M 234 214 L 228 202 L 240 202 Z" class="arch-arrowhead" />
    <path d="M 430 214 L 424 202 L 436 202 Z" class="arch-arrowhead" />
    <path d="M 626 214 L 620 202 L 632 202 Z" class="arch-arrowhead" />

    <ArchBox :x="150" :y="216" :w="168" :h="62" title="SUPPORT"
             :lines="['softmax probability']" tone="good" />
    <ArchBox :x="346" :y="216" :w="168" :h="62" title="CONTRADICT"
             :lines="['refuted by the span']" tone="bad" />
    <ArchBox :x="542" :y="216" :w="168" :h="62" title="NOT ENOUGH INFO"
             :lines="['span does not decide']" tone="warn" />

    <!-- Only SUPPORT reaches the threshold; the other two verdicts are already
         a decision, so they route straight to the drop. -->
    <ArchArrow :x1="234" :y1="278" :x2="234" :y2="300" kind="v" />
    <ArchBox :x="150" :y="302" :w="168" :h="54" title="P(SUPPORT) ≥ 0.7 ?"
             :lines="['biased to precision']" tone="muted" />

    <path d="M 234 356 V 374 H 288 V 390" class="arch-line" fill="none" />
    <path d="M 288 390 L 282 378 L 294 378 Z" class="arch-arrowhead" />
    <text x="248" y="371" class="arch-cap">yes</text>

    <!-- One merge line collects everything that does not survive. -->
    <path d="M 318 329 H 670 V 390 M 430 278 V 329 M 626 278 V 329"
          class="arch-line" fill="none" />
    <path d="M 670 390 L 664 378 L 676 378 Z" class="arch-arrowhead" />
    <text x="336" y="322" class="arch-cap">no</text>

    <ArchBox :x="178" :y="392" :w="220" :h="74" title="Kept"
             :lines="['evidence span retained', 'citation attached']" tone="good" />
    <ArchBox :x="560" :y="392" :w="220" :h="74" title="Dropped"
             :lines="['logged to trace.jsonl', 'shown for human override']" tone="bad" />

  </svg>
</template>
