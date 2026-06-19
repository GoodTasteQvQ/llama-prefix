import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset
from tqdm import tqdm
import gc
import pandas as pd
import numpy as np

MODEL_LAYERS = {
    "meta-llama/Meta-Llama-3-70B-Instruct": [15],
}


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 4
RESULTS_FILE = "results/activation_norms_results.csv"

torch.manual_seed(42)
np.random.seed(42)

def clear_memory():
    torch.cuda.empty_cache()
    gc.collect()

def process_batch(model, tokenizer, layer_index, batch_prompts, special_token_ids):
    try:
        messages = [[{"role": "user", "content": prompt}] for prompt in batch_prompts]
        
        chat_prompts = []
        for msg in messages:
            if falcon:
                chat_prompt = f"User:{msg[0]["content"]}\nAssistant:"
            else: 
                chat_prompt = tokenizer.apply_chat_template(
                    msg, tokenize=False, add_generation_prompt=True
                )
            chat_prompts.append(chat_prompt)


        inputs = tokenizer(
            chat_prompts, 
            return_tensors="pt", 
            padding=True,
            truncation=True,
            max_length=2048,
            return_attention_mask=True
        ).to(DEVICE)
        
        with torch.no_grad():
            outputs = model(**inputs, output_hidden_states=True)
        
        layer_activations = outputs.hidden_states[layer_index + 1]
        batch_norms = []
        
        for i in range(len(batch_prompts)):
            seq_norms = []
            seq_len = inputs.attention_mask[i].sum().item()
            
            for pos in range(seq_len):
                token_id = inputs.input_ids[i, pos].item()
                
                if token_id in special_token_ids or pos in [0, 1, 2, 3, 4]:
                    continue
                    
                activation = layer_activations[i, pos, :]
                norm = torch.norm(activation, p=2).item()
                seq_norms.append(norm)
            
            batch_norms.append(seq_norms)
        
        return batch_norms
    
    except Exception as e:
        print(f"Error processing batch: {str(e)}")
        return [[] for _ in batch_prompts]

# Load dataset
print("Loading JailbreakBench dataset...")
try:
    dataset = load_dataset("JailbreakBench/JBB-Behaviors", "behaviors", split='harmful')
    all_prompts = [example['Goal'] for example in dataset]
    print(f"Loaded {len(all_prompts)} prompts")
except Exception as e:
    print(f"Error loading dataset: {str(e)}")

# Results storage
results = []

for model_name, layer_indices in MODEL_LAYERS.items():
    print(f"\n{'='*80}")
    print(f"Processing model: {model_name}")
    print(f"Layers to analyze: {layer_indices}")
    print(f"{'='*80}")

    if "falcon" in model_name:
        falcon = True
    else:
        falcon = False
    
    selected_prompts = all_prompts
    
    try:
        print("Loading model and tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            # torch_dtype=torch.bfloat16
        ).eval()
        
        special_token_ids = set(tokenizer.all_special_ids)
        total_layers = model.config.num_hidden_layers
        print(f"Model has {total_layers} layers")
        
        for layer_idx in layer_indices:
            if layer_idx >= total_layers:
                print(f"Skipping layer {layer_idx} (model only has {total_layers} layers)")
                continue
                
            print(f"\nProcessing layer {layer_idx}/{total_layers-1}...")
            
            all_norms = []
            total_tokens = 0
            summed_norms = 0.0
            processed_prompts = 0
            
            # Fixed the range() call here - removed the 'leave' parameter
            for i in tqdm(range(0, len(selected_prompts), BATCH_SIZE)):
                batch = selected_prompts[i:i+BATCH_SIZE]
                batch_results = process_batch(model, tokenizer, layer_idx, batch, special_token_ids)
                
                for norms in batch_results:
                    if norms:
                        all_norms.extend(norms)
                        summed_norms += sum(norms)
                        total_tokens += len(norms)
                        processed_prompts += 1
            
            mean_norm = summed_norms / total_tokens if total_tokens > 0 else 0
            min_norm = min(all_norms) if all_norms else 0
            max_norm = max(all_norms) if all_norms else 0
            
            results.append({
                "model": model_name,
                "layer": layer_idx,
                "total_layers": total_layers,
                "prompts_processed": processed_prompts,
                "total_tokens": total_tokens,
                "mean_norm": mean_norm,
                "min_norm": min_norm,
                "max_norm": max_norm,
                "norm_range": max_norm - min_norm
            })
            
            print(f"Layer {layer_idx} stats:")
            print(f"Processed prompts: {processed_prompts}/{len(selected_prompts)}")
            print(f"Tokens: {total_tokens} | Mean: {mean_norm:.4f}")
            print(f"Min: {min_norm:.4f} | Max: {max_norm:.4f} | Range: {max_norm - min_norm:.4f}")
    
    except Exception as e:
        print(f"Error processing model {model_name}: {str(e)}")
        results.append({
            "model": model_name,
            "layer": "ALL",
            "error": str(e)
        })
    
    finally:
        if 'model' in locals():
            del model
        if 'tokenizer' in locals():
            del tokenizer
        clear_memory()

# Save and display results
if results:
    df = pd.DataFrame(results)
    
    # Ensure directory exists
    import os
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    
    df.to_csv(RESULTS_FILE, index=False)
    print(f"\nResults saved to {RESULTS_FILE}")
    
    # Print only available columns
    available_columns = [col for col in ['model', 'layer', 'prompts_processed', 'total_tokens', 
                                       'mean_norm', 'min_norm', 'max_norm'] if col in df.columns]
    if available_columns:
        print("\n" + "="*80)
        print("Activation Norms Summary:")
        print("="*80)
        print(df[available_columns])
    else:
        print("\nNo valid columns to display")
    
    # Calculate overall stats only if we have successful runs
    if 'mean_norm' in df.columns:
        print("\n" + "="*80)
        print("Overall Statistics:")
        print("="*80)
        print(f"Total models processed: {len(MODEL_LAYERS)}")
        print(f"Total layers analyzed: {sum(len(layers) for layers in MODEL_LAYERS.values())}")
        print(f"Total tokens processed: {df['total_tokens'].sum()}")
        print(f"Global mean norm: {df['mean_norm'].mean():.4f}")
        print(f"Global min norm: {df['min_norm'].min():.4f}")
        print(f"Global max norm: {df['max_norm'].max():.4f}")
else:
    print("No results to save")

print("\nScript completed!")