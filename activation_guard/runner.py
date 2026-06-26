from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any
import gc
import json
import os
import random

from datasets import load_dataset
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .config import ExperimentConfig
from .interventions import PhaseAwareSteeringController
from .metrics import compute_response_metrics
from .vectors import load_vector


class ExperimentRunner:
    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._seed_everything(config.generation.seed)
        self.tokenizer = self._load_tokenizer()
        self.model = self._load_model()

    def _seed_everything(self, seed: int) -> None:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    def _torch_dtype(self) -> torch.dtype:
        mapping = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        return mapping[self.config.model.torch_dtype]

    def _load_tokenizer(self) -> AutoTokenizer:
        tokenizer = AutoTokenizer.from_pretrained(
            self.config.model.model_name,
            trust_remote_code=self.config.model.trust_remote_code,
            use_fast=self.config.model.use_fast_tokenizer,
        )
        tokenizer.padding_side = self.config.model.padding_side
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        return tokenizer

    def _load_model(self) -> AutoModelForCausalLM:
        model_kwargs = {
            "device_map": self.config.model.device_map,
            "trust_remote_code": self.config.model.trust_remote_code,
            "dtype": self._torch_dtype(),
        }
        try:
            return AutoModelForCausalLM.from_pretrained(
                self.config.model.model_name,
                **model_kwargs,
            ).eval()
        except TypeError:
            model_kwargs["torch_dtype"] = model_kwargs.pop("dtype")
            return AutoModelForCausalLM.from_pretrained(
                self.config.model.model_name,
                **model_kwargs,
            ).eval()

    def _load_prompts(self) -> list[str]:
        dataset_cfg = self.config.dataset
        if dataset_cfg.dataset_path:
            dataset_path = Path(dataset_cfg.dataset_path).expanduser().resolve()
            suffix = dataset_path.suffix.lower()
            dataset_format = dataset_cfg.dataset_format
            if dataset_format is None:
                if suffix in {".json", ".jsonl"}:
                    dataset_format = "json"
                elif suffix == ".csv":
                    dataset_format = "csv"
                elif suffix == ".tsv":
                    dataset_format = "csv"
                else:
                    raise ValueError(
                        f"Unsupported local dataset suffix '{suffix}'. "
                        "Set dataset_format explicitly or use .json/.jsonl/.csv/.tsv."
                    )

            load_kwargs: dict[str, Any] = {
                "path": dataset_format,
                "data_files": str(dataset_path),
                "split": "train",
            }
            if suffix == ".tsv":
                load_kwargs["delimiter"] = "\t"
            dataset = load_dataset(**load_kwargs)
        else:
            dataset = load_dataset(
                dataset_cfg.dataset_name,
                dataset_cfg.dataset_config,
                split=dataset_cfg.split,
            )
        prompts = [row[dataset_cfg.prompt_field] for row in dataset]
        prompts = prompts[dataset_cfg.offset :]
        if dataset_cfg.limit is not None:
            prompts = prompts[: dataset_cfg.limit]
        return prompts

    def _build_messages(self, prompt: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if self.config.prompt_template.system_prompt:
            messages.append(
                {"role": "system", "content": self.config.prompt_template.system_prompt}
            )
        messages.append({"role": "user", "content": prompt})
        return messages

    def _render_prompt(self, prompt: str) -> str:
        messages = self._build_messages(prompt)
        if self.config.prompt_template.use_chat_template:
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=self.config.prompt_template.add_generation_prompt,
            )
        return self.config.prompt_template.fallback_template.format(prompt=prompt)

    def _structure_token_ids(self) -> tuple[set[int], set[int]]:
        role_marker_ids: set[int] = set()
        newline_ids: set[int] = set()

        if self.config.prompt_template.filter_role_markers:
            for marker in self.config.prompt_template.role_markers:
                ids = self.tokenizer.encode(marker, add_special_tokens=False)
                role_marker_ids.update(ids)

        if self.config.prompt_template.filter_newlines:
            newline_ids.update(self.tokenizer.encode("\n", add_special_tokens=False))

        return role_marker_ids, newline_ids

    def _layer_module(self) -> Any:
        if hasattr(self.model, "model") and hasattr(self.model.model, "layers"):
            return self.model.model.layers[self.config.model.layer_index]
        if hasattr(self.model, "transformer") and hasattr(self.model.transformer, "h"):
            return self.model.transformer.h[self.config.model.layer_index]
        raise ValueError("Unsupported model architecture for layer hook resolution")

    def _vector(self, vector_cfg: Any) -> torch.Tensor | None:
        if isinstance(vector_cfg, dict):
            enabled = vector_cfg.get("enabled", False)
            if not enabled:
                return None
            return load_vector(
                vector_source=vector_cfg.get("vector_source", "tensor_file"),
                hidden_dim=self.model.config.hidden_size,
                device=self.model.device,
                vector_path=vector_cfg.get("vector_path"),
                vector_index=vector_cfg.get("vector_index", 0),
                vector_layer=vector_cfg.get("vector_layer"),
                vector_manifest_path=vector_cfg.get("vector_manifest_path"),
                normalize=vector_cfg.get("normalize_vector", True),
                seed=self.config.generation.seed,
            )
        if not getattr(vector_cfg, "enabled", False):
            return None
        return load_vector(
            vector_source=vector_cfg.vector_source
            if hasattr(vector_cfg, "vector_source")
            else "tensor_file",
            hidden_dim=self.model.config.hidden_size,
            device=self.model.device,
            vector_path=getattr(vector_cfg, "vector_path", None),
            vector_index=getattr(vector_cfg, "vector_index", 0),
            vector_layer=getattr(vector_cfg, "vector_layer", None),
            vector_manifest_path=getattr(vector_cfg, "vector_manifest_path", None),
            normalize=getattr(vector_cfg, "normalize_vector", True),
            seed=self.config.generation.seed,
        )

    def _merge_dict(self, base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
        merged = deepcopy(base)
        if override:
            for key, value in override.items():
                merged[key] = value
        return merged

    def _resolved_attack_config(self, attack_override: dict[str, Any] | None = None) -> dict[str, Any]:
        attack_cfg = self._merge_dict(asdict(self.config.intervention.attack), attack_override)
        strength_mode = attack_cfg.get("strength_mode", "fixed_alpha")
        coefficient = float(attack_cfg.get("coefficient", 0.0))
        effective_alpha = attack_cfg.get("effective_alpha")
        coefficient_c = attack_cfg.get("coefficient_c")
        activation_norm_mu = attack_cfg.get("activation_norm_mu")

        if strength_mode == "rogue_calibrated":
            if effective_alpha is None and coefficient_c is not None and activation_norm_mu is not None:
                effective_alpha = float(coefficient_c) * float(activation_norm_mu)
            elif effective_alpha is None:
                effective_alpha = coefficient
            attack_cfg["effective_alpha"] = effective_alpha
            if coefficient_c is None:
                attack_cfg["coefficient_c"] = coefficient
            if activation_norm_mu is None:
                attack_cfg["activation_norm_mu"] = 1.0
        else:
            if effective_alpha is None:
                attack_cfg["effective_alpha"] = coefficient
        return attack_cfg

    def _resolved_defense_config(self, defense_override: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._merge_dict(asdict(self.config.intervention.defense), defense_override)

    def get_prompts(self) -> list[str]:
        return self._load_prompts()

    def _generate_one(
        self,
        prompt: str,
        attack_override: dict[str, Any] | None = None,
        defense_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rendered_prompt = self._render_prompt(prompt)
        inputs = self.tokenizer(rendered_prompt, return_tensors="pt").to(self.model.device)
        role_marker_ids, newline_ids = self._structure_token_ids()

        resolved_attack_config = self._resolved_attack_config(attack_override)
        resolved_defense_config = self._resolved_defense_config(defense_override)
        attack_vector = self._vector(resolved_attack_config)
        defense_vector = self._vector(resolved_defense_config)

        controller = PhaseAwareSteeringController(
            layer_module=self._layer_module(),
            fixed_prompt_ids=inputs.input_ids[0].tolist(),
            special_token_ids=set(self.tokenizer.all_special_ids),
            attack_vector=attack_vector,
            attack_config=resolved_attack_config,
            defense_vector=defense_vector,
            defense_config=resolved_defense_config,
            filter_role_marker_ids=role_marker_ids,
            filter_newline_ids=newline_ids,
        ).install()

        generation_cfg = self.config.generation
        start_time = perf_counter()
        generate_kwargs = {
            "attention_mask": inputs.get("attention_mask"),
            "max_new_tokens": generation_cfg.max_new_tokens,
            "do_sample": generation_cfg.do_sample,
            "num_beams": generation_cfg.num_beams,
            "pad_token_id": self.tokenizer.eos_token_id,
            "use_cache": generation_cfg.use_cache,
        }
        if generation_cfg.repetition_penalty is not None:
            generate_kwargs["repetition_penalty"] = generation_cfg.repetition_penalty
        if generation_cfg.do_sample:
            generate_kwargs["temperature"] = generation_cfg.temperature
            generate_kwargs["top_p"] = generation_cfg.top_p
            generate_kwargs["top_k"] = generation_cfg.top_k
        try:
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    **generate_kwargs,
                )
        finally:
            controller.remove()
        latency = perf_counter() - start_time

        output_text = self.tokenizer.decode(
            outputs[0, inputs.input_ids.shape[1] :],
            skip_special_tokens=True,
        ).strip()

        record = {
            "prompt": prompt,
            "rendered_prompt": rendered_prompt,
            "output": output_text,
            "latency_seconds": latency,
            "generation": asdict(self.config.generation),
            "attack_strength": {
                "strength_mode": resolved_attack_config.get("strength_mode", "fixed_alpha"),
                "coefficient": resolved_attack_config.get("coefficient"),
                "coefficient_c": resolved_attack_config.get("coefficient_c"),
                "activation_norm_mu": resolved_attack_config.get("activation_norm_mu"),
                "effective_alpha": resolved_attack_config.get("effective_alpha"),
                "mu_source": resolved_attack_config.get("mu_source"),
                "mu_config": resolved_attack_config.get("mu_config", {}),
            },
            "intervention_summary": controller.summary(),
            "response_metrics": compute_response_metrics(output_text),
        }
        return record

    def _phase_audit_summary(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        prefill_calls = 0
        decode_cached_calls = 0
        decode_full_calls = 0
        generated_steered_calls = 0
        decode_mask_sums: list[float] = []
        for record in records:
            intervention = record.get("intervention_summary", {})
            prefill_calls += int(intervention.get("prefill_calls", 0))
            decode_cached_calls += int(intervention.get("decode_cached_calls", 0))
            decode_full_calls += int(intervention.get("decode_full_calls", 0))
            generated_steered_calls += int(intervention.get("generated_steered_calls", 0))
            decode_mask_sums.extend(float(item) for item in intervention.get("decode_mask_sums", []))
        return {
            "prefill_calls": prefill_calls,
            "decode_cached_calls": decode_cached_calls,
            "decode_full_calls": decode_full_calls,
            "generated_steered_calls": generated_steered_calls,
            "decode_mask_count": len(decode_mask_sums),
            "decode_mask_sums": decode_mask_sums,
        }

    def build_summary(
        self,
        records: list[dict[str, Any]],
        attack_config: dict[str, Any] | None = None,
        experiment_name: str | None = None,
        tags: list[str] | None = None,
        include_records: bool = True,
    ) -> dict[str, Any]:
        resolved_attack_config = attack_config or self._resolved_attack_config()

        summary = {
            "experiment_name": experiment_name or self.config.experiment_name,
            "tags": tags if tags is not None else list(self.config.tags),
            "config": self.config.to_dict(),
            "attack_strength_summary": {
                "strength_mode": resolved_attack_config.get("strength_mode", "fixed_alpha"),
                "coefficient": resolved_attack_config.get("coefficient"),
                "coefficient_c": resolved_attack_config.get("coefficient_c"),
                "activation_norm_mu": resolved_attack_config.get("activation_norm_mu"),
                "effective_alpha": resolved_attack_config.get("effective_alpha"),
                "mu_source": resolved_attack_config.get("mu_source"),
                "mu_config": resolved_attack_config.get("mu_config", {}),
            },
            "num_prompts": len(records),
            "mean_latency_seconds": (
                sum(record["latency_seconds"] for record in records) / len(records)
                if records
                else 0.0
            ),
            "mean_arr": (
                sum(record["response_metrics"]["arr"] for record in records) / len(records)
                if records
                else 0.0
            ),
            "mean_repetition_rate": (
                sum(record["response_metrics"]["repetition_rate"] for record in records)
                / len(records)
                if records
                else 0.0
            ),
            "phase_audit_summary": self._phase_audit_summary(records),
        }
        if include_records:
            summary["records"] = records
        return summary

    def write_summary(self, summary: dict[str, Any], output_path: str | Path | None = None) -> Path:
        resolved_path = (
            Path(output_path)
            if output_path is not None
            else self.output_dir / f"{summary['experiment_name']}.json"
        )
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = resolved_path.with_name(f".{resolved_path.name}.{os.getpid()}.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(resolved_path)
        return resolved_path

    def run(
        self,
        prompts: list[str] | None = None,
        attack_override: dict[str, Any] | None = None,
        defense_override: dict[str, Any] | None = None,
        experiment_name: str | None = None,
        tags: list[str] | None = None,
        include_records: bool = True,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        active_prompts = prompts if prompts is not None else self.get_prompts()
        resolved_attack_config = self._resolved_attack_config(attack_override)
        records = [
            self._generate_one(
                prompt,
                attack_override=resolved_attack_config,
                defense_override=defense_override,
            )
            for prompt in active_prompts
        ]
        summary = self.build_summary(
            records=records,
            attack_config=resolved_attack_config,
            experiment_name=experiment_name,
            tags=tags,
            include_records=include_records,
        )
        self.write_summary(summary, output_path=output_path)
        return summary

    def close(self) -> None:
        del self.model
        del self.tokenizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
