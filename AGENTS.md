# AGENTS.md

Notes for agents/contributors working with this repo on specific hardware, based on
measurements on a real GPU. Doc-only — nothing here changes code or defaults.

## NVIDIA Tesla T4 (Turing, sm_75)

Measured on a real Tesla T4 16GB (driver 550.163.01, torch 2.5.1+cu121), default
Chatterbox-Turbo engine, commit `915ae28`.

- **Keep `TTS_BF16` off (the default) on T4 / other Turing (sm_75) cards.**
  `TTS_BF16=auto` enables bf16 whenever `torch.cuda.is_bf16_supported()` is `True`,
  and T4 reports `True` for that check — but Turing has no bf16-capable tensor
  cores, so bf16 falls back to a slow compute path instead of speeding things up.
  Measured warm RTF (wall-clock / audio-length, 5 warm runs each, <0.5% run-to-run
  variance): **0.335 fp32 (default) vs 0.535 bf16 (`TTS_BF16=on`/`auto`) — bf16 is
  ~1.6x slower.** bf16 does reduce peak VRAM (~3.9GB vs ~4.9GB), but on a 16GB
  card that headroom isn't needed. The README's "~40% throughput on bf16-capable
  GPUs" claim holds on Ampere+ (A100/A10/RTX 30xx+), not on Turing.
  This repo doesn't expose an fp16 path, so float32 (the default) is the best
  option on T4-class hardware.
- **The default Turbo engine ignores `exaggeration` and `cfg_weight`.** The
  `/tts` API and `config.generation_defaults` expose these as if they were always
  tunable, but Turbo logs `CFG, min_p and exaggeration are not supported by Turbo
  version and will be ignored` at runtime. If you need exaggeration/CFG control,
  switch to the Original or Multilingual engine instead of Turbo.
