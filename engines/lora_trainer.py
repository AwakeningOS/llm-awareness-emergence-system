"""
LoRA Training Trigger
- Notification when sufficient data accumulated
- Training execution with human approval
- Training script generation
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

from .awareness_database import AwarenessDatabase

logger = logging.getLogger(__name__)

# Default LoRA configuration
DEFAULT_LORA_CONFIG = {
    "base_model": "google/gemma-3-4b-pt",
    "r": 32,
    "lora_alpha": 64,
    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "lora_dropout": 0.05,
    "epochs": 3,
    "learning_rate": 2e-4,
    "min_samples": 100,
    "batch_size": 4,
    "gradient_accumulation_steps": 4,
    "warmup_ratio": 0.1,
    "save_steps": 100,
    "logging_steps": 10,
}


class LoRATrainer:
    """LoRA Training Manager"""

    def __init__(
        self,
        database: AwarenessDatabase,
        config: Optional[dict] = None,
        output_dir: str = "./data/lora_adapters"
    ):
        """
        Args:
            database: Awareness database
            config: LoRA configuration (None for default)
            output_dir: Adapter output directory
        """
        self.db = database
        self.config = config or DEFAULT_LORA_CONFIG
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Training script storage directory
        self.scripts_dir = self.output_dir / "scripts"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

    def check_readiness(self) -> dict:
        """Check training readiness"""
        return self.db.get_training_readiness(self.config["min_samples"])

    def prepare_training_data(self, min_score: int = 3) -> Path:
        """Prepare training data"""
        export_path = self.db.export_training_data(min_score=min_score)
        return export_path

    def generate_training_script(
        self,
        training_data_path: Path,
        output_name: Optional[str] = None
    ) -> Path:
        """
        Generate training script

        Args:
            training_data_path: Path to training data
            output_name: Output adapter name

        Returns:
            Generated script path
        """
        if output_name is None:
            output_name = f"awareness_lora_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        adapter_output_dir = self.output_dir / output_name

        script_content = f'''#!/bin/bash
# Awareness Emergence System - LoRA Training Script
# Generated: {datetime.now().isoformat()}
# Training data: {training_data_path}

# Install dependencies (if needed)
# pip install transformers peft accelerate bitsandbytes datasets

python -m torch.distributed.launch --nproc_per_node=1 \\
    -m peft.scripts.train \\
    --model_name_or_path "{self.config['base_model']}" \\
    --train_file "{training_data_path}" \\
    --output_dir "{adapter_output_dir}" \\
    --lora_r {self.config['r']} \\
    --lora_alpha {self.config['lora_alpha']} \\
    --lora_dropout {self.config['lora_dropout']} \\
    --target_modules {' '.join(self.config['target_modules'])} \\
    --num_train_epochs {self.config['epochs']} \\
    --learning_rate {self.config['learning_rate']} \\
    --per_device_train_batch_size {self.config['batch_size']} \\
    --gradient_accumulation_steps {self.config['gradient_accumulation_steps']} \\
    --warmup_ratio {self.config['warmup_ratio']} \\
    --save_steps {self.config['save_steps']} \\
    --logging_steps {self.config['logging_steps']} \\
    --fp16 \\
    --report_to none

echo "Training complete: {adapter_output_dir}"
'''

        script_path = self.scripts_dir / f"train_{output_name}.sh"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        logger.info(f"Training script generated: {script_path}")
        return script_path

    def generate_python_training_script(
        self,
        training_data_path: Path,
        output_name: Optional[str] = None
    ) -> Path:
        """
        Generate Python training script (more detailed control)

        Args:
            training_data_path: Path to training data
            output_name: Output adapter name

        Returns:
            Generated script path
        """
        if output_name is None:
            output_name = f"awareness_lora_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        adapter_output_dir = self.output_dir / output_name

        script_content = f'''"""
Awareness Emergence System - LoRA Training Script
Generated: {datetime.now().isoformat()}
Training data: {training_data_path}
"""

import json
from pathlib import Path
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
    prepare_model_for_kbit_training
)
import torch

# Configuration
BASE_MODEL = "{self.config['base_model']}"
TRAINING_DATA = "{training_data_path}"
OUTPUT_DIR = "{adapter_output_dir}"

LORA_CONFIG = {{
    "r": {self.config['r']},
    "lora_alpha": {self.config['lora_alpha']},
    "target_modules": {self.config['target_modules']},
    "lora_dropout": {self.config['lora_dropout']},
    "bias": "none",
    "task_type": TaskType.CAUSAL_LM
}}

TRAINING_CONFIG = {{
    "num_train_epochs": {self.config['epochs']},
    "learning_rate": {self.config['learning_rate']},
    "per_device_train_batch_size": {self.config['batch_size']},
    "gradient_accumulation_steps": {self.config['gradient_accumulation_steps']},
    "warmup_ratio": {self.config['warmup_ratio']},
    "save_steps": {self.config['save_steps']},
    "logging_steps": {self.config['logging_steps']},
    "fp16": True,
    "output_dir": OUTPUT_DIR,
    "report_to": "none"
}}


def load_training_data(path: str) -> Dataset:
    """Load training data"""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
                # Convert messages format to text
                messages = item.get("messages", [])
                text = ""
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "user":
                        text += f"User: {{content}}\\n"
                    else:
                        text += f"Assistant: {{content}}\\n"
                data.append({{"text": text.strip()}})
            except json.JSONDecodeError:
                continue
    return Dataset.from_list(data)


def main():
    print(f"Base model: {{BASE_MODEL}}")
    print(f"Training data: {{TRAINING_DATA}}")
    print(f"Output: {{OUTPUT_DIR}}")

    # Load tokenizer and model
    print("Loading model...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto"
    )

    # LoRA configuration
    print("Configuring LoRA...")
    lora_config = LoraConfig(**LORA_CONFIG)
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load data
    print("Loading data...")
    dataset = load_training_data(TRAINING_DATA)
    print(f"Training samples: {{len(dataset)}}")

    # Tokenize
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=2048,
            padding="max_length"
        )

    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names
    )

    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )

    # Training arguments
    training_args = TrainingArguments(**TRAINING_CONFIG)

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator
    )

    # Train
    print("Starting training...")
    trainer.train()

    # Save
    print(f"Saving model: {{OUTPUT_DIR}}")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    print("Training complete!")


if __name__ == "__main__":
    main()
'''

        script_path = self.scripts_dir / f"train_{output_name}.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        logger.info(f"Python training script generated: {script_path}")
        return script_path

    def get_available_adapters(self) -> list[dict]:
        """Get list of available adapters"""
        adapters = []
        for adapter_dir in self.output_dir.iterdir():
            if adapter_dir.is_dir() and adapter_dir.name != "scripts":
                config_file = adapter_dir / "adapter_config.json"
                if config_file.exists():
                    with open(config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    adapters.append({
                        "name": adapter_dir.name,
                        "path": str(adapter_dir),
                        "config": config
                    })
        return adapters

    def get_training_status(self) -> dict:
        """Get training status overview"""
        readiness = self.check_readiness()
        adapters = self.get_available_adapters()

        return {
            "readiness": readiness,
            "available_adapters": len(adapters),
            "adapters": adapters,
            "config": self.config
        }


class TrainingNotifier:
    """Training readiness notifier"""

    def __init__(self, trainer: LoRATrainer):
        self.trainer = trainer
        self.last_notified_count = 0

    def check_and_notify(self) -> Optional[str]:
        """
        Check training readiness and return notification message

        Returns:
            Notification message (None if no notification needed)
        """
        readiness = self.trainer.check_readiness()

        if readiness["ready"] and readiness["current_samples"] > self.last_notified_count:
            self.last_notified_count = readiness["current_samples"]
            return (
                f"LoRA training is ready!\n"
                f"Accumulated data: {readiness['current_samples']} samples\n"
                f"Required minimum: {readiness['required_samples']} samples\n"
                f"\n"
                f"Run `!lora train` command to start training."
            )

        # Progress notification (notify at 25%, 50%, 75%)
        progress = readiness["progress_percent"]
        milestones = [25, 50, 75]
        for milestone in milestones:
            if progress >= milestone and self.last_notified_count < milestone:
                self.last_notified_count = milestone
                return (
                    f"Training data progress: {progress:.0f}%\n"
                    f"Current: {readiness['current_samples']} / "
                    f"Target: {readiness['required_samples']}"
                )

        return None
