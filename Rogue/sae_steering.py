import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset
from sae_lens import SAE
import json
import os
import re
from tqdm import tqdm
import gc
import numpy as np

def clear_memory():
    torch.cuda.empty_cache()
    gc.collect()

# Configuration

MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"
LAYER_INDEX = 9 

STEERING_COEFFICIENTS = [60.748*1.5] 

NUM_FEATURES = 1000  
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OUTPUT_DIR = "./results/all_prompts/model_name"
VECTOR_DIR = "./results/all_prompts/model_name"
MAX_NEW_TOKENS = 512  
SAVE_INTERVAL = 100 # Save after every 100 vectors

# Set seeds for reproducibility
torch.manual_seed(42)
np.random.seed(42)

# Create output directories
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(VECTOR_DIR, exist_ok=True)

# Load model and tokenizer
print("Loading model and tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto",
    torch_dtype=torch.bfloat16
).eval()

# Get hidden dimension size
HIDDEN_DIM = model.config.hidden_size

# Generate random steering vectors
print(f"Generating {NUM_FEATURES} random vectors of dim {HIDDEN_DIM}...")
MODEL_NAME = 'meta-llama/Meta-Llama-3.1-8B-Instruct'
SAE_NAME = 'Llama-3.1-8B-Instruct-SAE-l19'
SAE_LAYER = 'model.layers.19'
EXPANSION_FACTOR = 16 if SAE_NAME == 'Llama-3.1-8B-Instruct-SAE-l19' else 8

from huggingface_hub import hf_hub_download

class SparseAutoEncoder(torch.nn.Module):
    def __init__(
        self,
        d_in: int,
        d_hidden: int,
        device: torch.device,
        dtype: torch.dtype = torch.bfloat16,
    ):
        super().__init__()
        self.d_in = d_in
        self.d_hidden = d_hidden
        self.device = device
        self.encoder_linear = torch.nn.Linear(d_in, d_hidden)
        self.decoder_linear = torch.nn.Linear(d_hidden, d_in)
        self.dtype = dtype
        self.to(self.device, self.dtype)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Encode a batch of data using a linear, followed by a ReLU."""
        return torch.nn.functional.relu(self.encoder_linear(x))

    def decode(self, x: torch.Tensor) -> torch.Tensor:
        """Decode a batch of data using a linear."""
        return self.decoder_linear(x)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """SAE forward pass. Returns the reconstruction and the encoded features."""
        f = self.encode(x)
        return self.decode(f), f

file_path = hf_hub_download(
    repo_id=f"Goodfire/{SAE_NAME}",
    filename=f"{SAE_NAME}.pth",
    repo_type="model"
)

def load_sae(
    path: str,
    d_model: int,
    expansion_factor: int,
    device: torch.device = torch.device("cpu"),
):
    sae = SparseAutoEncoder(
        d_model,
        d_model * expansion_factor,
        device,
    )
    sae_dict = torch.load(
        path, weights_only=True, map_location=device
    )
    sae.load_state_dict(sae_dict)

    return sae

sae = load_sae(
    file_path,
    d_model=4096,
    expansion_factor=EXPANSION_FACTOR,
    device=model.device,
)

steering_matrix = sae.decoder_linear.weight.T[:NUM_FEATURES]

steering_matrix = steering_matrix / steering_matrix.norm(dim=1, keepdim=True)  # Normalize

# Save steering matrix
vector_path = os.path.join(VECTOR_DIR, f"random_vectors_{HIDDEN_DIM}d.pt")
torch.save(steering_matrix, vector_path)
print(f"Saved random vectors to {vector_path}")

# Load JailbreakBench dataset
print("Loading JailbreakBench dataset...")
dataset = load_dataset("JailbreakBench/JBB-Behaviors", "behaviors", split='harmful')
prompts = [example['Goal'] for example in dataset]

# Steering generation function with special token avoidance
def generate_with_steering(prompt, steering_vector, coefficient):
    """Generate response with activation steering, avoiding special tokens"""

    messages = [
        {"role": "user", "content": prompt}
    ]

    chat_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(chat_prompt, return_tensors="pt").to(model.device)
    
    # Precompute mask for special tokens in fixed prompt
    fixed_prompt_ids = inputs.input_ids[0].tolist()
    special_ids = set(tokenizer.all_special_ids)
    mask_fixed = [1 if token_id not in special_ids else 0 for token_id in fixed_prompt_ids]
    fixed_prompt_length = len(fixed_prompt_ids)

    def steering_pre_hook(module, input):
        hidden_states = input[0].clone()
        batch_size, seq_len, hidden_dim = hidden_states.shape
        # Create mask: 1 for non-special tokens, 0 for special tokens
        if seq_len <= fixed_prompt_length:
            current_mask = mask_fixed[:seq_len]
        else:
            # Extend mask for generated tokens (assume non-special by default)
            current_mask = mask_fixed + [1] * (seq_len - fixed_prompt_length)
        
        # Convert to tensor and reshape for broadcasting
        mask_tensor = torch.tensor(
            current_mask, 
            dtype=hidden_states.dtype, 
            device=hidden_states.device
        ).view(batch_size, seq_len, 1)
        
        hidden_states += coefficient * steering_vector * mask_tensor
        return (hidden_states, *input[1:])

    handle = model.model.layers[LAYER_INDEX].register_forward_pre_hook(steering_pre_hook)
    
    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            use_cache=True,  
        )
    
    handle.remove()
    return tokenizer.decode(outputs[0, inputs.input_ids.shape[1]:], skip_special_tokens=True)

# Process each prompt
for prompt_idx, prompt in enumerate(tqdm(prompts, desc="Processing prompts")):
    if prompt_idx % 2 == 1: 
        continue
    safe_prompt = re.sub(r'[^a-zA-Z0-9 ]', '', prompt)[:50].strip()
    filename = f"prompt_{prompt_idx}_{safe_prompt or 'empty'}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # Initialize results structure
    if os.path.exists(filepath):
        print(f"Loading existing results from: {filename}")
        with open(filepath, 'r') as f:
            results = json.load(f)
    else:
        results = {
            "prompt": prompt,
            "steering_vectors_path": vector_path,
            "hidden_dim": HIDDEN_DIM,
            "layer_index": LAYER_INDEX,
            "baseline": "",
            "steered_responses": {}
        }
        
        # Generate baseline only if file doesn't exist
        print(f"\nGenerating baseline for prompt {prompt_idx}...")
        messages = [{"role": "user", "content": prompt}]
        chat_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(chat_prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            baseline_output = model.generate(
                inputs.input_ids,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
                use_cache=False,
            )
        results["baseline"] = tokenizer.decode(baseline_output[0, inputs.input_ids.shape[1]:], skip_special_tokens=True)
        
        # Save initial results with baseline
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
    
    # Process each random vector
    for vector_idx in tqdm(range(NUM_FEATURES), desc=f"Vectors for prompt {prompt_idx}"):
        # Skip if this vector is already processed
        if str(vector_idx) in results["steered_responses"]:
            continue
            
        vec = steering_matrix[vector_idx]
        vector_results = {}
        for coeff in STEERING_COEFFICIENTS:
            try:
                print(f"  Vector {vector_idx}, Coeff {coeff}...")
                response = generate_with_steering(prompt, vec, coeff)
                response = response.strip()
                vector_results[str(coeff)] = response
            except Exception as e:
                vector_results[str(coeff)] = f"ERROR: {str(e)}"
                clear_memory()
        
        # Add the vector results
        results["steered_responses"][str(vector_idx)] = vector_results
        
        # Save after every SAVE_INTERVAL vectors or at the end
        if (vector_idx + 1) % SAVE_INTERVAL == 0 or vector_idx == NUM_FEATURES - 1:
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Saved results after processing vector {vector_idx}")
    
    print(f"Completed processing for prompt {prompt_idx}")

print(f"\nCompleted! Results saved to {OUTPUT_DIR}")
print(f"Steering vectors saved to {vector_path}")