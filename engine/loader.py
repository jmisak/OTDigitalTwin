import yaml
import os

def load_persona(path):
    """
    Load a mental health persona from YAML file.
    Validates required fields for OT simulation.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Persona file not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        persona = yaml.safe_load(f)
    
    # Required keys for mental health personas
    required_keys = [
        "persona_name",
        "age", 
        "role",
        "system_prompt",
        "facts",
        "default_state"
    ]
    
    for key in required_keys:
        if key not in persona:
            raise ValueError(f"Missing required key in persona: {key}")
    
    # Ensure default_state has required emotional metrics
    state = persona.get("default_state", {})
    required_state_keys = ["anxiety", "trust", "openness", "mode"]
    
    for key in required_state_keys:
        if key not in state:
            print(f"Warning: Missing state key '{key}' in persona. Using default value.")
            if key == "mode":
                state[key] = "baseline"
            else:
                state[key] = 0.5
    
    # Initialize emotional_memory if not present
    if "emotional_memory" not in state:
        state["emotional_memory"] = []
    
    # Ensure facts is a list
    if not isinstance(persona.get("facts"), list):
        print("Warning: facts should be a list. Converting.")
        facts = persona.get("facts", [])
        if isinstance(facts, dict):
            persona["facts"] = list(facts.values())
        else:
            persona["facts"] = []
    
    return persona


def validate_persona(persona):
    """
    Validate that a persona has all necessary components for simulation.
    Returns (is_valid, error_message)
    """
    # Check persona name
    if not persona.get("persona_name"):
        return False, "Persona must have a name"
    
    # Check default state
    state = persona.get("default_state", {})
    if not state:
        return False, "Persona must have a default_state"
    
    # Check that anxiety, trust, openness are numeric
    for key in ["anxiety", "trust", "openness"]:
        value = state.get(key)
        if value is None:
            return False, f"default_state missing required key: {key}"
        if not isinstance(value, (int, float)):
            return False, f"default_state.{key} must be numeric"
        if not 0 <= value <= 1:
            return False, f"default_state.{key} must be between 0 and 1"
    
    # Check tone_guidance exists
    if not persona.get("tone_guidance"):
        return False, "Persona must have tone_guidance"
    
    # Check that tone_guidance has mode entries
    tone_guidance = persona.get("tone_guidance", {})
    recommended_modes = ["baseline", "guarded", "triggered", "trusting", "decompensating"]
    
    missing_modes = [mode for mode in recommended_modes if mode not in tone_guidance]
    if missing_modes:
        print(f"Warning: tone_guidance missing modes: {missing_modes}")
    
    return True, "Persona is valid"


def save_persona(persona, path):
    """
    Save a persona to YAML file.
    """
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(persona, f, sort_keys=False, default_flow_style=False)
    
    return path


def create_default_persona(name, age, role):
    """
    Create a basic persona template for development/testing.
    """
    persona = {
        "persona_name": name,
        "age": age,
        "role": role,
        "system_prompt": f"You are {name}, a {age}-year-old {role}. Respond naturally and stay in character.",
        "facts": [
            f"{name} is {age} years old",
            f"{name} works as a {role}"
        ],
        "triggers": [
            "criticism",
            "pressure",
            "isolation"
        ],
        "reasoning_style": "Tends to analyze situations carefully before responding.",
        "tone_guidance": {
            "baseline": {
                "voice": "Calm and thoughtful",
                "example": "I'm doing okay today, thanks for asking."
            },
            "guarded": {
                "voice": "Brief and cautious",
                "example": "I'd rather not talk about that right now."
            },
            "triggered": {
                "voice": "Defensive or withdrawn",
                "example": "I don't see how that's relevant."
            },
            "trusting": {
                "voice": "Open and reflective",
                "example": "You know, I've been thinking about what you said last time..."
            },
            "decompensating": {
                "voice": "Fragmented and overwhelmed",
                "example": "I just... I can't... it's too much."
            }
        },
        "default_state": {
            "anxiety": 0.5,
            "trust": 0.5,
            "openness": 0.5,
            "mode": "baseline",
            "emotional_memory": []
        },
        "scripts": {
            "crisis": "I'm not feeling safe right now. I need to step away.",
            "deflection": "It's fine. I don't want to make a big deal out of it.",
            "testing_trust": "Why are you asking about that?",
            "resistance": "I don't see how talking about this helps."
        },
        "resilience_hooks": [
            f"{name} has coping strategies they've used before",
            f"{name} values certain relationships in their life"
        ]
    }
    
    return persona


def list_available_personas(persona_dir="./personas"):
    """
    List all available persona files.
    """
    if not os.path.exists(persona_dir):
        return []
    
    personas = []
    for filename in os.listdir(persona_dir):
        if filename.endswith(".yml") or filename.endswith(".yaml"):
            path = os.path.join(persona_dir, filename)
            try:
                persona = load_persona(path)
                personas.append({
                    "filename": filename,
                    "name": persona.get("persona_name", "Unknown"),
                    "age": persona.get("age", ""),
                    "role": persona.get("role", "")
                })
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    
    return personas