"""Train a LoRA adapter on a chosen licensed causal model. Not run by packaging."""

import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-model",
        required=True,
        help="Model with a chat template; check its license and language coverage",
    )
    p.add_argument(
        "--revision", required=True, help="Exact model commit SHA for reproducibility"
    )
    p.add_argument(
        "--output", required=True, help="New directory outside the source checkout"
    )
    p.add_argument("--epochs", type=float, default=2)
    p.add_argument("--max-length", type=int, default=2048)
    args = p.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        p.error("Output must be a new directory to avoid overwriting weights")
    if len(args.revision) != 40 or any(
        c not in "0123456789abcdef" for c in args.revision.lower()
    ):
        p.error("Use the full model commit SHA")
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    set_seed(42)
    root = Path(__file__).resolve().parents[1]
    tok = AutoTokenizer.from_pretrained(
        args.base_model, revision=args.revision, trust_remote_code=False
    )
    if not tok.chat_template:
        raise ValueError("Base tokenizer needs a chat template")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        revision=args.revision,
        trust_remote_code=False,
        torch_dtype=torch.bfloat16
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        else torch.float32,
    )
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules="all-linear",
            task_type="CAUSAL_LM",
        ),
    )

    def load(split):
        encoded = []
        for line in (root / "data" / f"{split}.jsonl").read_text().splitlines():
            messages = json.loads(line)["messages"]
            full = tok.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=False
            )
            prefix = tok.apply_chat_template(
                messages[:-1], tokenize=True, add_generation_prompt=True
            )
            if full[: len(prefix)] != prefix:
                raise ValueError(
                    "Template does not support safe prefix masking; "
                    "adapt preprocessing for this model"
                )
            if len(full) > args.max_length:
                raise ValueError(
                    "Example exceeds max length; increase it rather than "
                    "silently truncating the answer"
                )
            labels = [-100] * len(prefix) + full[len(prefix) :]
            if all(x == -100 for x in labels):
                raise ValueError("No assistant tokens to train")
            encoded.append(
                {"input_ids": full, "attention_mask": [1] * len(full), "labels": labels}
            )
        return Dataset.from_list(encoded)

    def collate(batch):
        length = max(len(x["input_ids"]) for x in batch)
        return {
            k: torch.tensor(
                [
                    x[k]
                    + (
                        [tok.pad_token_id]
                        if k == "input_ids"
                        else [0]
                        if k == "attention_mask"
                        else [-100]
                    )
                    * (length - len(x[k]))
                    for x in batch
                ]
            )
            for k in ("input_ids", "attention_mask", "labels")
        }

    train, valid = load("train"), load("validation")
    settings = TrainingArguments(
        output_dir=str(output),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-5,
        logging_steps=1,
        save_strategy="epoch",
        eval_strategy="epoch",
        report_to="none",
        seed=42,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
    )
    trainer = Trainer(
        model=model,
        args=settings,
        train_dataset=train,
        eval_dataset=valid,
        data_collator=collate,
    )
    trainer.train()
    trainer.save_model(str(output))
    tok.save_pretrained(str(output))
    (output / "training_provenance.json").write_text(json.dumps(vars(args), indent=2))
    print(
        "Adapter saved. This is not a standalone model; retain "
        "the exact base model. Evaluate before deployment."
    )


if __name__ == "__main__":
    main()
