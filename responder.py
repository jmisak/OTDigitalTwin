import json
import os
import re
import threading
import torch
from engine.drift import get_current_mode, apply_response_effects, generate_teaching_note

from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer

# -----------------------------
# Dispatcher
# -----------------------------

def generate_response(student_prompt, persona, conversation_history, force_mode=None):
    """
    Generate a response from the client persona using AI or fallback logic.
    Priority (when not forced): HF (local transformers) > Claude API > Local Templates
    Returns: (response_text, updated_state, teaching_note)
    """
    try:
        # Explicitly forced to local templates
        if force_mode == "Templates (Local)":
            print("FORCED: Using local templates")
            return generate_response_local(student_prompt, persona, conversation_history)

        # Explicitly forced to AI (local transformers)
        if force_mode == "AI":
            print("FORCED: Using Hugging Face transformers (AI)")
            return generate_response_hf(student_prompt, persona, conversation_history)

        # Default priority order if no force_mode
        if os.getenv("HF_TOKEN"):
            print("DEBUG: Attempting Hugging Face transformers generation...")
            return generate_response_hf(student_prompt, persona, conversation_history)

        if os.getenv("ANTHROPIC_API_KEY"):
            print("DEBUG: Attempting Claude API generation...")
            return generate_response_claude(student_prompt, persona, conversation_history)

        print("DEBUG: Falling back to local templates")
        return generate_response_local(student_prompt, persona, conversation_history)

    except Exception as e:
        from engine.utils import safe_log
        safe_log("Response generation error", str(e))
        # If user explicitly asked for AI, don’t silently fall back
        if force_mode == "AI":
            raise
        return generate_response_local(student_prompt, persona, conversation_history)

# -----------------------------
# Local Transformers Generation
# -----------------------------

# Candidate models optimized for HF Spaces (smaller, faster models)
# These models are specifically chosen for:
# - Small size (< 1GB) for fast loading
# - Good instruction following
# - Fast inference on CPU
# PRIORITIZED FOR SPEED: TinyLlama first (1.1B = 2.5x faster than Phi-2)
MODEL_CANDIDATES = [
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0", # 1.1B params, very fast - PRIORITY FOR SPEED
    "microsoft/phi-2",                    # 2.7B params, excellent quality but slower
    "facebook/opt-350m",                   # 350M params, fast fallback
    "distilgpt2",                          # 82M params, extremely fast
]

_TOKENIZER = None
_MODEL = None
_MODEL_NAME = None

def _select_dtype():
    """Select appropriate dtype based on available hardware."""
    if torch.cuda.is_available():
        return torch.float16  # Use float16 for GPU (faster than bfloat16 on most GPUs)
    return torch.float32      # CPU uses float32

def _ensure_model_loaded():
    """Load the most suitable model for the current environment."""
    global _TOKENIZER, _MODEL, _MODEL_NAME
    if _TOKENIZER is not None:
        return

    last_error = None
    for model_name in MODEL_CANDIDATES:
        try:
            print(f"Loading model: {model_name}")
            _TOKENIZER = AutoTokenizer.from_pretrained(
                model_name,
                use_fast=True,
                trust_remote_code=True  # Some models like Phi-2 need this
            )

            # Add padding token if not present
            if _TOKENIZER.pad_token is None:
                _TOKENIZER.pad_token = _TOKENIZER.eos_token

            # Load model with optimizations for HF Spaces
            _MODEL = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=_select_dtype(),
                device_map="auto",
                low_cpu_mem_usage=True,  # Optimize memory usage
                trust_remote_code=True    # Some models need this
            )

            # Set to eval mode for inference
            _MODEL.eval()

            _MODEL_NAME = model_name
            print(f"✓ Loaded {model_name} successfully")
            return
        except Exception as e:
            last_error = e
            print(f"✗ Failed to load {model_name}: {str(e)[:200]}")
            continue
    raise RuntimeError(f"Could not load any candidate model. Last error: {last_error}")

import re
import threading
import torch
from transformers import TextIteratorStreamer

def _select_relevant_facts(facts, prompt, count=5):
    """
    Select most relevant facts based on prompt content.
    Returns a mix of always-relevant facts and prompt-specific ones.
    """
    if not facts:
        return []

    prompt_lower = prompt.lower()
    scored_facts = []

    # Keywords to look for in prompt
    keywords = {
        'work': ['work', 'job', 'boss', 'career', 'coworker', 'supervisor', 'shift', 'office', 'construction'],
        'family': ['family', 'dad', 'mom', 'brother', 'sister', 'parent', 'son', 'daughter', 'wife', 'husband'],
        'pain': ['pain', 'hurt', 'ache', 'injury', 'physical', 'body', 'knee', 'back'],
        'mental': ['feel', 'stress', 'anxiety', 'panic', 'worry', 'scared', 'overwhelm'],
        'social': ['friend', 'people', 'social', 'lonely', 'isolated', 'relationship'],
        'leisure': ['hobby', 'fun', 'enjoy', 'free time', 'weekend', 'relax', 'game', 'gaming'],
        'future': ['future', 'plan', 'goal', 'retirement', 'college', 'next', 'change'],
        'money': ['money', 'afford', 'cost', 'expensive', 'financial', 'save', 'pay']
    }

    for fact in facts:
        fact_str = str(fact)
        fact_lower = fact_str.lower()
        score = 1  # Base score

        # Check for keyword matches
        for category, words in keywords.items():
            if any(word in prompt_lower for word in words):
                if any(word in fact_lower for word in words):
                    score += 2

        scored_facts.append((score, fact_str))

    # Sort by relevance, take top facts
    scored_facts.sort(reverse=True, key=lambda x: x[0])
    return [fact for score, fact in scored_facts[:count]]

def _check_triggers(prompt, triggers):
    """
    Check if prompt contains potentially triggering content.
    Returns True if triggers detected.
    """
    if not triggers:
        return False

    prompt_lower = prompt.lower()
    for trigger in triggers:
        trigger_lower = str(trigger).lower()
        # Check for key phrases from trigger
        trigger_words = trigger_lower.split()[:3]  # First few words often most relevant
        if any(word in prompt_lower for word in trigger_words if len(word) > 3):
            return True
    return False

def generate_response_hf(prompt, persona, conversation_history, stream_callback=None):
    """
    Generate a deeply persona-grounded response using local transformers.
    Leverages rich persona data for authentic, psychologically complex responses.
    Supports optional streaming via stream_callback.
    """
    _ensure_model_loaded()

    name = persona.get("persona_name", "Client")
    age = persona.get("age", "")
    role = persona.get("role", "")
    state = persona.get("default_state", {}) or {}
    mode = get_current_mode(state)

    # Apply response effects
    state = apply_response_effects(state, prompt)
    mode = get_current_mode(state)

    # Extract rich persona elements
    system_prompt = persona.get("system_prompt", "").strip()
    facts = persona.get("facts", [])
    triggers = persona.get("triggers", [])
    reasoning_style = persona.get("reasoning_style", "").strip()
    resilience_hooks = persona.get("resilience_hooks", [])

    # Get tone guidance for current mode
    tone_guidance = persona.get("tone_guidance", {}).get(mode, {})
    tone_voice = tone_guidance.get("voice", "Natural and authentic")
    tone_example = tone_guidance.get("example", "")

    # Select most relevant facts (mix of general and specific to prompt)
    selected_facts = _select_relevant_facts(facts, prompt, count=3)  # Reduced from 5 for faster processing

    # Check if prompt might trigger defensive response
    is_potentially_triggering = _check_triggers(prompt, triggers)

    # Extract current situation from emotional memory or conversation history
    current_situation = "Normal day, no specific external stressors right now"
    if state.get("emotional_memory"):
        for memory in reversed(state["emotional_memory"]):
            if memory.startswith("context:"):
                current_situation = memory.replace("context:", "").strip()
                break

    # Build conversation context (last 2 turns for faster processing)
    context = ""
    if conversation_history:
        for turn in conversation_history[-2:]:  # Reduced from 3 to 2 for speed
            if "student" in turn and "client" in turn:
                context += f"Student: {turn['student']}\n{name}: {turn['client']}\n\n"

    # Build optimized instruction (reduced tokens for speed)
    instruction = f"""You are {name}, {age}, {role}. In OT therapy session.

RESPOND as {name} only. 5-6 sentences. Be authentic. NO analysis or questions.

BACKGROUND: {system_prompt}

LIFE CONTEXT:
{chr(10).join(f'• {fact}' for fact in selected_facts)}

CURRENT SITUATION: {current_situation}

EMOTIONAL STATE ({mode}): Anxiety {state.get('anxiety', 0.5):.2f}, Trust {state.get('trust', 0.5):.2f}, Openness {state.get('openness', 0.5):.2f}

TONE: {tone_voice} Example: "{tone_example}"

"""

    if context:
        instruction += f"""CONVERSATION SO FAR:
{context}"""

    instruction += f"""Student: {prompt}
{name}:"""


    # Tokenize
    inputs = _TOKENIZER(instruction, return_tensors="pt", padding=True, truncation=True).to(_MODEL.device)

    # Streaming setup
    streamer = TextIteratorStreamer(_TOKENIZER, skip_prompt=True, skip_special_tokens=True) if stream_callback else None

    generation_kwargs = {
        "input_ids": inputs["input_ids"],
        "attention_mask": inputs["attention_mask"],
        "max_new_tokens": 70,    # Optimized for 5-6 sentences (10-12 words each) - SPEED PRIORITY
        "min_length": 40,        # Ensure minimum response quality
        "temperature": 0.7,      # Optimized for speed while maintaining variety
        "top_p": 0.85,           # Faster sampling, still good quality
        "do_sample": True,
        "use_cache": True,       # Reuse attention computations for speed
        "streamer": streamer,
        "pad_token_id": _TOKENIZER.eos_token_id or _TOKENIZER.pad_token_id,
        "eos_token_id": _TOKENIZER.eos_token_id,  # Explicit early stopping
        "repetition_penalty": 1.1,  # Reduced from 1.15 for faster generation
    }

    response_text = ""

    # Use inference mode for better performance
    with torch.inference_mode():
        if streamer:
            def _consume():
                nonlocal response_text
                for token_text in streamer:
                    response_text += token_text
                    try:
                        stream_callback(token_text)
                    except Exception:
                        pass
            thread = threading.Thread(target=_consume, daemon=True)
            thread.start()
            _MODEL.generate(**generation_kwargs)
            thread.join()
        else:
            outputs = _MODEL.generate(**generation_kwargs)
            raw_text = _TOKENIZER.decode(outputs[0], skip_special_tokens=True)
            # Strip any echoed instruction
            response_text = raw_text.replace(instruction, "").strip()

    # Clean response
    response_text = response_text.strip()
    response_text = re.sub(r'---.*?---', '', response_text)   # remove separators
    response_text = re.sub(r'\[.*?\]', '', response_text)     # remove bracketed notes
    response_text = re.sub(r'^(Student:|' + re.escape(name) + ':)', '', response_text).strip()

    # Truncate at first sign of role switch
    for stop_token in [f"Student:", f"\nStudent:", f"\n\nStudent:", f"\n{name}:", f"\n\n{name}:"]:
        if stop_token in response_text:
            response_text = response_text.split(stop_token)[0].strip()
            break

    # Remove meta-commentary (questions for students, analysis, etc.)
    # Stop at any meta-questions or analysis markers
    meta_markers = [
        "<|Question|>", "<|Answer|>", "<|Analysis|>",
        "<|beginning", "<|end", "<|template", "<|conversation",  # Template markers
        "\n(a)", "\n(b)", "\n(c)",  # Lettered questions
        " : ", ": Identify", ": What", ": How", ": Why", ": Describe",  # Colon-separated analysis
        "[Answer:", "[Question:", "[Analysis:",  # Bracketed sections
        "What emotions", "How might", "Why do you think",  # Question stems
        "This response shows", "Notice how", "Observe that",  # Analysis stems
        "Identify the elements", "What possible factors", "Consider how"  # More analysis patterns
    ]
    for marker in meta_markers:
        if marker in response_text:
            response_text = response_text.split(marker)[0].strip()
            break

    # Additional cleanup: remove anything after double colon or bracket patterns
    response_text = re.sub(r'\s*:\s*[A-Z][^.!?]*\?.*$', '', response_text, flags=re.DOTALL)  # Remove ": Question..." patterns
    response_text = re.sub(r'\[Answer:.*$', '', response_text, flags=re.DOTALL)  # Remove [Answer: ...] patterns
    response_text = re.sub(r'\[Question:.*$', '', response_text, flags=re.DOTALL)  # Remove [Question: ...] patterns
    response_text = re.sub(r'<\|[^|]*\|>.*$', '', response_text, flags=re.DOTALL)  # Remove <|anything|> patterns

    # Guard against instruction leakage
    if response_text.lower().startswith("be sure to") or "use correct" in response_text.lower():
        response_text = "I'm doing alright today. Just keeping things running, like always."
    
    if not response_text:
        response_text = "Sorry, I didn’t catch that. Could you rephrase?"

    # Update emotional memory
    if "emotional_memory" in state:
        if not isinstance(state["emotional_memory"], list):
            state["emotional_memory"] = []
        tag = f"{mode}:neutral"
        state["emotional_memory"].append(tag)
        state["emotional_memory"] = state["emotional_memory"][-5:]

    # Teaching note
    teaching_note = generate_teaching_note(state, prompt, mode)
    teaching_note += f"\n\n💡 Response generated locally with Transformers ({_MODEL_NAME})."

    return response_text, state, teaching_note


def generate_response_claude(student_prompt, persona, conversation_history):
    """
    Generate response using Claude API (optional premium feature).
    """
    try:
        import anthropic
        
        state = persona.get("default_state", {})
        mode = get_current_mode(state)
        
        # Apply response effects to state
        state = apply_response_effects(state, student_prompt)
        mode = get_current_mode(state)
        
        # Build prompts
        system_prompt = build_system_prompt_for_ai(persona, state, mode)
        conversation_context = build_conversation_context(conversation_history)
        
        # Call Claude API
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=400,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"{conversation_context}\n\nOT Student: {student_prompt}"}
            ]
        )
        
        response_text = message.content[0].text
        
        # Update emotional memory
        if "emotional_memory" in state:
            if not isinstance(state["emotional_memory"], list):
                state["emotional_memory"] = []
            memory_tag = determine_memory_tag(student_prompt, mode, state)
            state["emotional_memory"].append(memory_tag)
            state["emotional_memory"] = state["emotional_memory"][-5:]
        
        teaching_note = generate_teaching_note(state, student_prompt, mode)
        teaching_note += "\n\n✨ Response generated using Claude AI (Premium)"
        
        return response_text, state, teaching_note
        
    except Exception as e:
        from engine.utils import safe_log
        safe_log("Claude API error", str(e))
        return generate_response_local(student_prompt, persona, conversation_history)


def generate_response_local(student_prompt, persona, conversation_history):
    """
    Local response generation using persona templates and state-based selection.
    Fallback when no AI available or as primary mode.
    """
    state = persona.get("default_state", {})
    mode = get_current_mode(state)
    name = persona.get("persona_name", "Client")
    
    # Apply response effects to state
    state = apply_response_effects(state, student_prompt)
    
    # Update mode after response effects
    mode = get_current_mode(state)
    
    # Select response based on mode and prompt analysis
    response = select_response_template(
        student_prompt,
        name,
        mode,
        state,
        persona,
        conversation_history
    )
    
    # Update emotional memory
    if "emotional_memory" in state:
        if not isinstance(state["emotional_memory"], list):
            state["emotional_memory"] = []
        
        memory_tag = determine_memory_tag(student_prompt, mode, state)
        state["emotional_memory"].append(memory_tag)
        state["emotional_memory"] = state["emotional_memory"][-5:]
    
    # Generate teaching note
    teaching_note = generate_teaching_note(state, student_prompt, mode)
    teaching_note += "\n\n🔧 Response generated using template system (Local)"
    
    return response, state, teaching_note


def build_system_prompt_for_ai(persona, state, mode, student_input):
    """
    Build a detailed system prompt for AI models to generate in-character responses.
    """
    name = persona.get("persona_name", "Client")
    age = persona.get("age", "")
    role = persona.get("role", "")

    # Get tone guidance for current mode
    tone_guidance = persona.get("tone_guidance", {}).get(mode, {})
    tone_voice = tone_guidance.get("voice", "Natural and authentic")
    tone_example = tone_guidance.get("example", "")

    # Get some facts about the persona
    facts = persona.get("facts", [])
    key_facts = facts[:5] if isinstance(facts, list) else []

    # Build system prompt
    system_prompt = f"""You are {name}, a {age}-year-old {role}. You are talking to an occupational therapy student.

CRITICAL INSTRUCTIONS:
- Respond ONLY as {name} – ONE response, then STOP
- Do NOT generate both sides of the conversation
- Do NOT include multiple turns or dialogue
- Your response should be 2–5 sentences maximum
- Stay completely in character

YOUR BACKGROUND:
{chr(10).join(f"- {fact}" for fact in key_facts)}

CURRENT EMOTIONAL STATE:
- Anxiety: {state.get('anxiety', 0):.2f}/1.0
- Trust: {state.get('trust', 0):.2f}/1.0
- Openness: {state.get('openness', 0):.2f}/1.0

HOW TO RESPOND ({mode} mode):
{tone_voice}
Example: "{tone_example}"

Now begin the conversation:
Student: {student_input}
{name}:"""

    return prompt


def build_conversation_context(history):
    """Build context from conversation history for AI models."""
    if not history:
        return "This is the beginning of the conversation."
    
    context = "Previous conversation:\n"
    for i, turn in enumerate(history[-3:], 1):  # Last 3 turns
        if "student" in turn:
            context += f"Student: {turn['student']}\n"
        if "client" in turn:
            context += f"You: {turn['client']}\n"
    
    return context

def handle_greeting(name, mode, state, persona):
    """Generate responses for initial greetings."""
    if name == "Jack":
        if mode == "guarded":
            return "Hey. So... what exactly are we doing here?"
        else:
            return "Hi. I'm Jack. Not really sure what to expect from this, but... yeah, here I am."
    else:  # Maya
        if mode == "anxious_but_functional":
            return "Hi. Um, thanks for meeting with me. I've been... well, things have been a lot lately."
        else:
            return "Hello. I'm Maya. I appreciate you taking the time to talk with me."

def select_response_template(prompt, name, mode, state, persona, history):
    """
    Select and customize a response based on the current mode and prompt content.
    Used for local fallback when AI is unavailable.
    """
    prompt_lower = prompt.lower()
    
    # Handle greetings/introductions FIRST
    if not history and any(word in prompt_lower for word in ["hi", "hello", "hey", "good morning", "good afternoon"]):
        return handle_greeting(name, mode, state, persona)
        
    # Check for specific scenario triggers
    if is_crisis_query(prompt_lower) and mode == "decompensating":
        scripts = persona.get("scripts", {})
        return scripts.get("crisis", "I don't feel safe right now. I need to pause.")
    
    # Check if prompt is about specific topics
    if any(word in prompt_lower for word in ["work", "job", "boss", "brother", "supervisor"]):
        return handle_work_topic(name, mode, state, persona, prompt_lower)
    
    if any(word in prompt_lower for word in ["pain", "hurt", "physical", "body"]):
        return handle_pain_topic(name, mode, state, persona)
    
    if any(word in prompt_lower for word in ["feel", "feeling", "emotion"]):
        return handle_feelings_topic(name, mode, state, persona, prompt_lower)
    
    if any(word in prompt_lower for word in ["family", "dad", "sister", "parent"]):
        return handle_family_topic(name, mode, state, persona)
    
    # Default mode-based responses
    return get_mode_based_response(name, mode, state, persona)


def is_crisis_query(prompt_lower):
    """Check if the prompt is asking about crisis/safety."""
    crisis_terms = ["safe", "hurt yourself", "suicide", "end", "can't take"]
    return any(term in prompt_lower for term in crisis_terms)


def handle_work_topic(name, mode, state, persona, prompt_lower):
    """Generate responses about work-related topics."""
    if name == "Jack":
        if mode == "triggered" or mode == "guarded":
            return "I'd rather not get into it. Work is work, you know?"
        elif mode == "trusting":
            return "My brother's been on my case all week. It's like... I can't do anything right in his eyes. And my dad just backs him up because 'he's the foreman.' It's frustrating."
        else:
            return "Work's... fine. Same stuff, different day. Framing houses, dealing with Mike being Mike."
    else:  # Maya
        if mode == "triggered" or mode == "guarded":
            return "It's just work stress. Everyone deals with it, right?"
        elif mode == "trusting":
            return "Honestly? I feel like I'm drowning. Between agency work and freelance projects, I'm just... constantly behind. And my review is coming up, so there's that pressure too."
        else:
            return "Work's been busy. Lots of deadlines. The usual design agency chaos."


def handle_pain_topic(name, mode, state, persona):
    """Generate responses about physical pain."""
    pain_level = state.get("physical_discomfort", 0.5)
    
    if name == "Jack":
        if pain_level > 0.6:
            if mode == "trusting":
                return "My knee's been killing me lately. Some days I'm limping by noon. I used to be able to do so much more physically, and now... yeah, it's frustrating."
            else:
                return "It's whatever. I just take some ibuprofen and push through. Not like I have a choice."
        else:
            return "Knee's okay today. Manageable."
    else:  # Maya
        if pain_level > 0.6:
            if mode == "trusting":
                return "The headaches are almost daily now, and my wrists hurt when I'm working. I keep thinking, what if I'm doing permanent damage? But I can't afford to stop working."
            else:
                return "I get headaches sometimes. Probably just from staring at screens all day. Everyone in design deals with it."
        else:
            return "Physically I'm okay. Just the usual screen fatigue."


def handle_feelings_topic(name, mode, state, persona, prompt_lower):
    """Generate responses about emotions and feelings."""
    anxiety = state.get("anxiety", 0.5)
    
    if mode == "decompensating":
        return "I don't... everything's just a lot right now. I can't really explain it. I'm just overwhelmed."
    
    if mode == "triggered" or mode == "guarded":
        if "about" in prompt_lower:
            return "I don't know. Fine, I guess?"
        else:
            return "I'm fine. Just tired."
    
    if mode == "trusting":
        if name == "Jack":
            if anxiety > 0.6:
                return "Honestly? Anxious. Like there's this constant pressure I can't shake. Work, family expectations, feeling stuck... it all just builds up."
            else:
                return "Better than I have been, actually. Still stressed, but like... manageable stress?"
        else:  # Maya
            if anxiety > 0.6:
                return "Overwhelmed, mostly. And scared that I'm not good enough for this. Everyone else seems to handle everything so much better than me."
            else:
                return "I'm doing okay. Some days are harder than others, but I'm managing."
    
    return "I'm alright. Just dealing with the usual stuff."


def handle_family_topic(name, mode, state, persona):
    """Generate responses about family relationships."""
    if name == "Jack":
        if mode == "triggered":
            return "Can we talk about something else?"
        elif mode == "trusting":
            return "My dad and I mostly just coexist. He works a lot, I work a lot. My brother... that's complicated since he's also my boss. Mom moved to Arizona years ago."
        else:
            return "Family's fine. Nothing new there."
    else:  # Maya
        if mode == "triggered":
            return "I don't really want to get into family stuff right now."
        elif mode == "trusting":
            return "My parents are supportive but they don't really understand creative work. My sister's a nurse practitioner and everyone's always comparing us. It's... yeah, it's a thing."
        else:
            return "Family's good. I talk to them pretty regularly."


def get_mode_based_response(name, mode, state, persona):
    """Generate generic response based on current emotional mode."""
    resilience_hooks = persona.get("resilience_hooks", [])
    scripts = persona.get("scripts", {})
    
    if mode == "decompensating":
        return scripts.get("crisis", "I need to step away. This is too much right now.")
    
    if mode == "triggered":
        return scripts.get("resistance", "I'm not really in the mood to talk about this.")
    
    if mode == "guarded":
        return scripts.get("deflection", "It's not that deep. I'm just tired.")
    
    if mode == "trusting" and resilience_hooks:
        return f"You know what? {resilience_hooks[0]}"
    
    if mode == "recovering":
        return "I'm feeling a bit better actually. Still working through things, but... yeah, better."
    
    # Baseline
    return "I'm doing okay. What did you want to talk about?"


def determine_memory_tag(prompt, mode, state):
    """Generate an emotional memory tag based on the interaction."""
    prompt_lower = prompt.lower()
    
    if mode == "trusting":
        if any(word in prompt_lower for word in ["understand", "hear you", "makes sense"]):
            return "felt validated"
        return "felt safe to open up"
    
    if mode == "triggered":
        if any(word in prompt_lower for word in ["should", "need to", "why don't"]):
            return "felt criticized"
        return "felt defensive"
    
    if mode == "guarded":
        return "felt cautious"
    
    if mode == "decompensating":
        return "felt overwhelmed"
    
    return "shared thoughts"