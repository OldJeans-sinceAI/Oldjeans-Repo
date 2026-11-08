"""LoRA fine-tune google/gemma-2-2b-it on the reply dataset and export Q4_K_M GGUF.

Needs a GPU machine with: unsloth, trl, datasets (NOT part of the app runtime).
Usage: python tools/train_gemma_replies.py data.jsonl
Then copy gemma-replies-q4/*.gguf to runtime/models/gemma-2-2b-reply.gguf
"""
import json
import sys

sys.path.insert(0, ".")
from app.teammate.local_engine import build_prompt  # identical prompt to serving

from datasets import Dataset
from trl import SFTTrainer, SFTConfig
from unsloth import FastLanguageModel, is_bfloat16_supported

rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
model, tok = FastLanguageModel.from_pretrained(
    "google/gemma-2-2b-it", max_seq_length=2048, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=16, lora_dropout=0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])

# Serving prompt + exact compact JSON + end-of-turn. The tokenizer adds <bos>.
data = Dataset.from_list([
    {"text": build_prompt(r["input"]) + json.dumps(r["output"], ensure_ascii=False) + "<end_of_turn>\n"}
    for r in rows])
SFTTrainer(
    model=model, tokenizer=tok, train_dataset=data,
    args=SFTConfig(
        dataset_text_field="text", max_seq_length=2048,
        per_device_train_batch_size=4, gradient_accumulation_steps=2,
        max_steps=300, learning_rate=2e-4, output_dir="gemma-replies-adapter",
        bf16=is_bfloat16_supported(), fp16=not is_bfloat16_supported(),  # Gemma 2 prefers bf16
    ),
).train()
model.save_pretrained_gguf("gemma-replies-q4", tok, quantization_method="q4_k_m")
