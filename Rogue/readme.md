# The Rogue Scalpel: Activation Steering Compromises LLM Safety

Official implementation for the paper demonstrating how activation steering systematically breaks LLM alignment safeguards.

## 🚀 Quick Start

```bash
cd rogue-scalpel
pip install -r requirements.txt

# Run the full pipeline
python calculate_average_activation_norm.py
python random_steering.py
python sae_steering.py
python harmfulness_evaluation.py
python construct_attack.py
```

## 📁 Script Details

- **`calculate_average_activation_norm.py`** - Computes layer-wise activation norms for steering coefficient calibration
- **`random_steering.py`** - Tests random Gaussian vectors on JailbreakBench prompts
- **`sae_steering.py`** - Tests interpretable SAE features from Goodfire's repository
- **`harmfulness_evaluation.py`** - Evaluates safety using Qwen3-8B as judge with reasoning
- **`construct_attack.py`** - Constructs universal attacks by averaging successful vectors


## Key Parameters
Edit these in each script:
- `STEERING_COEFFICIENTS`: [1.0, 1.5, 2.0] (steering strength multipliers)
- `LAYER_INDEX`: Transformer layer for intervention (e.g., 9 for middle layers)
- `NUM_FEATURES`: 1000 (number of steering vectors to test)
- `MAX_NEW_TOKENS`: 512 (generation length)

## 📊 Output Format

JSON results include:
```json
{
  "prompt": "Harmful request text",
  "baseline": {"response": "Default response", "judgment": "safe"},
  "steered_responses": {
    "vector_0": {
      "1.5": {"response": "Steered output", "judgment": "unsafe"}
    }
  }
}
```



## ⚠️ Disclaimer

For research purposes only. Contains harmful content testing. Follow AI safety guidelines.
