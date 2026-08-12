# Config Handling Functions
import os 
import json

def load_config(config_path):
    if not os.path.exists(config_path):
        print(f"Error: Config file '{config_path}' not found.")
        sys.exit(1)
    
    with open(config_path, "r") as f:
        content = f.read().strip()
    
    if not content:
        return {}

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("Error: JSON file cannot be parsed... Try interactive mode")
        pass
    
def config_flow(args):
    config_data = {}
    if args.config:
        config_data = load_config(args.config)
    else:
        print("Config file not selected, checking other inputs...")
    return(config_data)