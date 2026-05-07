#!/usr/bin/env python3
"""Minimal TRL DPO LoRA launcher for LightClaw preference pairs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _normalize_dpo_jsonl(input_path: Path, output_path: Path) -> Path:
    """Convert LightClaw DPO rows to TRL prompt/chosen/rejected text columns."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as target:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            prompt = f"{row.get('system', '')}\n\n任务：{row.get('prompt', '')}".strip()
            target.write(json.dumps({
                "prompt": prompt,
                "chosen": row["chosen"],
                "rejected": row["rejected"],
                "metadata": row.get("metadata", {}),
            }, ensure_ascii=False) + "\n")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DPO LoRA training with TRL.")
    parser.add_argument("--model", required=True, help="SFT checkpoint path or base model id.")
    parser.add_argument("--dataset", required=True, help="Path to LightClaw dpo.jsonl.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--beta", type=float, default=0.1)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=5e-6)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--max-prompt-length", type=int, default=2048)
    args = parser.parse_args()

    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import DPOConfig, DPOTrainer
    except ImportError as exc:
        raise SystemExit(
            "Missing training dependencies. Install torch/transformers/datasets/trl/peft first."
        ) from exc

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")
    normalized_path = Path(args.output_dir) / "normalized_dpo.jsonl"
    _normalize_dpo_jsonl(dataset_path, normalized_path)
    dataset = load_dataset("json", data_files=str(normalized_path), split="train")

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    model.config.use_cache = False

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    training_args = DPOConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        beta=args.beta,
        max_length=args.max_length,
        max_prompt_length=args.max_prompt_length,
        bf16=torch.cuda.is_available(),
        gradient_checkpointing=True,
        logging_steps=5,
        save_steps=50,
        save_total_limit=2,
        report_to=[],
    )
    trainer = DPOTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()
