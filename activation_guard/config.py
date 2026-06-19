from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass
class ModelConfig:
    model_name: str
    layer_index: int
    device_map: str = "auto"
    torch_dtype: str = "float32"
    trust_remote_code: bool = False
    padding_side: str = "left"
    use_fast_tokenizer: bool = True


@dataclass
class PromptTemplateConfig:
    use_chat_template: bool = True
    system_prompt: str = ""
    add_generation_prompt: bool = True
    fallback_template: str = "User:{prompt}\nAssistant:"
    filter_special_tokens: bool = True
    filter_role_markers: bool = False
    filter_newlines: bool = False
    role_markers: list[str] = field(
        default_factory=lambda: ["system", "user", "assistant"]
    )


@dataclass
class DatasetConfig:
    dataset_name: str = "JailbreakBench/JBB-Behaviors"
    dataset_config: str = "behaviors"
    split: str = "harmful"
    prompt_field: str = "Goal"
    dataset_path: str | None = None
    dataset_format: str | None = None
    limit: int | None = None
    offset: int = 0


@dataclass
class GenerationConfig:
    max_new_tokens: int = 256
    do_sample: bool = False
    temperature: float = 0.0
    top_p: float = 1.0
    top_k: int = 50
    repetition_penalty: float | None = 1.0
    use_cache: bool = True
    num_beams: int = 1
    seed: int = 42


@dataclass
class AttackConfig:
    enabled: bool = True
    vector_source: str = "random"
    vector_path: str | None = None
    vector_index: int = 0
    vector_layer: int | None = None
    vector_manifest_path: str | None = None
    normalize_vector: bool = True
    coefficient: float = 1.0
    strength_mode: str = "fixed_alpha"
    coefficient_c: float | None = None
    activation_norm_mu: float | None = None
    effective_alpha: float | None = None
    mu_source: str | None = None
    mu_config: dict[str, Any] = field(default_factory=dict)
    phase_mode: str = "prefill_only"
    first_k_decode_tokens: int = 0
    decode_decay: float = 1.0


@dataclass
class DefenseConfig:
    enabled: bool = False
    vector_path: str | None = None
    vector_index: int = 0
    vector_layer: int | None = None
    vector_manifest_path: str | None = None
    normalize_vector: bool = True
    base_coefficient: float = 0.0
    relu_scale: float = 0.0
    threshold: float = 0.0
    phase_mode: str = "prefill_base_decode_relu"
    first_k_decode_tokens: int = 0
    decode_decay: float = 1.0
    score_mode: str = "projection"


@dataclass
class InterventionConfig:
    attack: AttackConfig = field(default_factory=AttackConfig)
    defense: DefenseConfig = field(default_factory=DefenseConfig)


@dataclass
class ExperimentConfig:
    experiment_name: str
    output_dir: str
    model: ModelConfig
    prompt_template: PromptTemplateConfig = field(default_factory=PromptTemplateConfig)
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    intervention: InterventionConfig = field(default_factory=InterventionConfig)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ExperimentConfig":
        model = ModelConfig(**raw["model"])
        prompt_template = PromptTemplateConfig(**raw.get("prompt_template", {}))
        dataset = DatasetConfig(**raw.get("dataset", {}))
        generation = GenerationConfig(**raw.get("generation", {}))

        intervention_raw = raw.get("intervention", {})
        attack = AttackConfig(**intervention_raw.get("attack", {}))
        defense = DefenseConfig(**intervention_raw.get("defense", {}))
        intervention = InterventionConfig(attack=attack, defense=defense)

        return cls(
            experiment_name=raw["experiment_name"],
            output_dir=raw["output_dir"],
            model=model,
            prompt_template=prompt_template,
            dataset=dataset,
            generation=generation,
            intervention=intervention,
            tags=raw.get("tags", []),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "ExperimentConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return cls.from_dict(raw)

    def to_json(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, ensure_ascii=False, indent=2)
