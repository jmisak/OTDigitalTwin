def apply_context_shift(persona, scenario):
    """
    Apply contextual scenario effects to persona's current state.
    This simulates how external events affect the client's emotional state.
    """
    state = persona.get("default_state", {})
    effects = scenario.get("effects", {})
    
    # Apply each effect with bounds checking
    for key, change in effects.items():
        if key in state and isinstance(state[key], (int, float)):
            current_value = state[key]
            new_value = current_value + change
            # Clamp between 0 and 1
            state[key] = max(0.0, min(1.0, round(new_value, 3)))
    
    # Add context to emotional memory if it exists
    if "emotional_memory" in state:
        if not isinstance(state["emotional_memory"], list):
            state["emotional_memory"] = []
        state["emotional_memory"].append(
            f"context: {scenario.get('description', scenario.get('scenario'))}"
        )
        # Keep only last 5 memories
        state["emotional_memory"] = state["emotional_memory"][-5:]
    
    return persona


def get_current_mode(state):
    """
    Determine the client's current emotional mode based on state values.
    This helps select appropriate response templates and tone.
    """
    anxiety = state.get("anxiety", 0.5)
    trust = state.get("trust", 0.5)
    openness = state.get("openness", 0.5)
    
    # Crisis threshold
    if anxiety > 0.8:
        return "decompensating"
    
    # Defensive/triggered
    if anxiety > 0.6 and openness < 0.3:
        return "triggered"
    
    # Guarded but present
    if trust < 0.4 and openness < 0.5:
        return "guarded"
    
    # Opening up
    if trust > 0.6 and openness > 0.6:
        return "trusting"
    
    # Recovering/hopeful
    if anxiety < 0.4 and trust > 0.5:
        return "recovering"
    
    # Baseline
    return "baseline"


def calculate_state_change(current_state, student_response):
    """
    Calculate how the student's response affects the client's emotional state.
    This is a simplified heuristic - in production, would use more sophisticated NLP.
    """
    
    response_lower = student_response.lower()
    changes = {}

    if hasattr(student_response, 'value'):
        student_response = student_response.value
    student_response = str(student_response) if student_response is not None else ""
    
    response_lower = student_response.lower()
    
    # Positive indicators (validation, open questions, empathy)
    validating_words = ["understand", "sounds like", "seems", "feel", "must be", "makes sense"]
    open_questions = ["tell me more", "what's that like", "how", "what"]
    empathy_phrases = ["hard", "difficult", "challenging", "tough"]
    
    # Negative indicators (advice-giving, minimizing, interrogating)
    advice_words = ["should", "need to", "have to", "must", "why don't you"]
    minimizing = ["just", "simply", "easy", "only", "at least"]
    closed_questions = ["did you", "have you", "are you", "do you"]
    
    validation_score = sum(1 for word in validating_words if word in response_lower)
    open_q_score = sum(1 for phrase in open_questions if phrase in response_lower)
    empathy_score = sum(1 for phrase in empathy_phrases if phrase in response_lower)
    
    advice_score = sum(1 for word in advice_words if word in response_lower)
    minimizing_score = sum(1 for word in minimizing if word in response_lower)
    
    # Calculate changes
    positive_impact = (validation_score * 0.05 + open_q_score * 0.04 + empathy_score * 0.03)
    negative_impact = (advice_score * 0.08 + minimizing_score * 0.06)
    
    changes["trust"] = positive_impact - negative_impact
    changes["openness"] = positive_impact * 0.8 - negative_impact * 0.5
    changes["anxiety"] = negative_impact * 0.5 - positive_impact * 0.3
    
    # Response length consideration (too short or too long can be problematic)
    word_count = len(student_response.split())
    if word_count < 5:
        changes["openness"] = changes.get("openness", 0) - 0.05
    elif word_count > 100:
        changes["anxiety"] = changes.get("anxiety", 0) + 0.05
    
    return changes


def apply_response_effects(state, student_response):
    """
    Apply the effects of the student's response to the client's state.
    """
    changes = calculate_state_change(state, student_response)
    
    # ADD THIS SAFEGUARD:
    if hasattr(student_response, 'value'):
        student_response = student_response.value
    student_response = str(student_response) if student_response is not None else ""
    
    changes = calculate_state_change(state, student_response)
    for key, change in changes.items():
        if key in state and isinstance(state[key], (int, float)):
            current_value = state[key]
            new_value = current_value + change
            state[key] = max(0.0, min(1.0, round(new_value, 3)))
    
    return state


def generate_teaching_note(state, student_response, mode):
    """
    Generate teaching feedback based on the interaction.
    """
    response_lower = student_response.lower()
    notes = []
    
    # Check for common issues
    if any(word in response_lower for word in ["should", "need to", "have to"]):
        notes.append("⚠️ Advice-giving detected. Consider asking open questions instead of giving directives.")
    
    if any(word in response_lower for word in ["just", "simply", "only"]):
        notes.append("⚠️ Potential minimizing language. Avoid words that might diminish the client's experience.")
    
    if response_lower.count("?") > 2:
        notes.append("⚠️ Multiple questions detected. Consider asking one question at a time to avoid overwhelming the client.")
    
    if len(student_response.split()) < 10:
        notes.append("💡 Very brief response. Consider adding validation or reflection before asking questions.")
    
    # Check for strengths
    if any(phrase in response_lower for phrase in ["sounds like", "seems", "hear you"]):
        notes.append("✅ Good use of reflection and validation.")
    
    if "tell me more" in response_lower or "what's that like" in response_lower:
        notes.append("✅ Effective use of open-ended questions.")
    
    # Mode-specific feedback
    if mode == "triggered" and state.get("trust", 0) < 0.4:
        notes.append("📊 Client is defensive. Consider backing off and focusing on rapport building.")
    
    if mode == "trusting" and state.get("openness", 0) > 0.6:
        notes.append("📊 Strong therapeutic alliance forming. This is a good time to explore deeper issues.")
    
    if mode == "decompensating":
        notes.append("🚨 Client may be in crisis. Assess safety and consider referral to crisis services.")
    
    if not notes:
        notes.append("✅ Solid therapeutic response. Continue building rapport.")
    
    return "\n".join(notes)