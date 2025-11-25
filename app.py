import gradio as gr
import yaml
import json
import os
import traceback
import matplotlib.pyplot as plt
import numpy as np

# Audio features disabled (not functional)
# import tempfile
# import speech_recognition as sr
# from TTS.api import TTS
# tts_model = TTS("tts_models/en/ljspeech/tacotron2-DDC")

#persona_voices = {
#    "Maya": "p225",     # younger female
#    "Robert": "p240",   # older male
#    "Angela": "p231",   # middle-aged female
#    "Jack": "p260"      # younger male
#}

from engine.loader import load_persona
from engine.drift import apply_context_shift
from engine.responder import generate_response
from engine.utils import safe_log
from engine.logger import log_interaction
import random

# Paths
persona_dir = "./personas"
contexts_path = "./contexts/scenarios.json"
error_log_path = "./ot_simulator_errors.log"

# Load available personas
def get_persona_choices():
    return [f for f in os.listdir(persona_dir) if f.endswith(".yml")]

# Load available contextual scenarios
def get_scenario_choices():
    try:
        with open(contexts_path, "r") as f:
            scenarios = json.load(f)
        return [s["scenario"] for s in scenarios]
    except Exception as e:
        safe_log("Scenarios load error", str(e))
        return []

# Generate radar chart for emotional/behavioral states
def plot_state(state, persona_name):
    if persona_name == "Jack":
        metrics = ["anxiety", "trust", "openness", "physical_discomfort"]
        colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
    elif persona_name == "Maya":
        metrics = ["anxiety", "trust", "creative_engagement", "occupational_balance"]
        colors = ["#e74c3c", "#3498db", "#9b59b6", "#1abc9c"]
    else:
        metrics = ["anxiety", "trust", "openness", "engagement"]
        colors = ["#e74c3c", "#3498db", "#2ecc71", "#95a5a6"]
    
    values = [state.get(m, 0.0) for m in metrics]
    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    ax.plot(angles, values, color=colors[0], linewidth=2)
    ax.fill(angles, values, color=colors[0], alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics])
    ax.set_ylim(0, 1)
    ax.set_yticklabels(['0.0', '0.2', '0.4', '0.6', '0.8', '1.0'])
    ax.set_title(f"{persona_name}'s Emotional State", fontsize=14, pad=20)
    ax.grid(True)
    fig.tight_layout()

    chart_path = f"./state_chart_{persona_name}.png"
    fig.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    return chart_path

# Generate interaction history visualization
def plot_interaction_history(history):
    if not history or len(history) < 2:
        return None
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6))
    
    interactions = list(range(1, len(history) + 1))
    anxiety_vals = [h.get('anxiety', 0) for h in history]
    trust_vals = [h.get('trust', 0) for h in history]
    
    ax1.plot(interactions, anxiety_vals, marker='o', color='#e74c3c', linewidth=2, label='Anxiety')
    ax1.set_ylabel('Anxiety Level', fontsize=10)
    ax1.set_ylim(0, 1)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')
    
    ax2.plot(interactions, trust_vals, marker='o', color='#3498db', linewidth=2, label='Trust')
    ax2.set_xlabel('Interaction Number', fontsize=10)
    ax2.set_ylabel('Trust Level', fontsize=10)
    ax2.set_ylim(0, 1)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right')
    
    fig.suptitle('Therapeutic Relationship Over Time', fontsize=14)
    fig.tight_layout()
    
    history_path = "./interaction_history.png"
    fig.savefig(history_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
    return history_path

# Generate smart response suggestions
def generate_suggestions(conversation_history, state_history, selected_persona_file):
    """Generate contextual response suggestions for students."""
    if not conversation_history:
        # First interaction suggestions
        return """### 💬 Suggested Opening Approaches

**Option 1 - Warm Introduction:**
"Hi, I'm [your name], an occupational therapy student. I'm here to support you. How are you doing today?"

**Option 2 - Purpose Clarification:**
"Hello! I'm [name], studying occupational therapy. I'm wondering what brings you here today?"

**Option 3 - Collaborative Start:**
"Hi [client name], thanks for meeting with me. What would be most helpful to talk about today?"
"""

    # Get persona and current state
    persona_path = os.path.join(persona_dir, selected_persona_file)
    persona = load_persona(persona_path)
    current_state = state_history[-1] if state_history else {}

    anxiety = current_state.get('anxiety', 0.5)
    trust = current_state.get('trust', 0.5)
    openness = current_state.get('openness', 0.5)

    suggestions = "### 💡 Suggested Therapeutic Responses\n\n"

    # Contextual suggestions based on emotional state
    if trust < 0.4:
        suggestions += "**🔨 Build Trust:**\n"
        suggestions += '- "I appreciate you sharing that with me. That takes courage."\n'
        suggestions += '- "I\'m here to support you, not judge. Your experiences matter."\n'
        suggestions += '- "What you\'re feeling makes complete sense given what you\'ve described."\n\n'

    if anxiety > 0.6:
        suggestions += "**😌 Reduce Anxiety:**\n"
        suggestions += '- "I notice this might be bringing up some difficult feelings. Would you like to take a moment?"\n'
        suggestions += '- "There\'s no rush. We can talk about this at whatever pace feels right for you."\n'
        suggestions += '- "What would help you feel more comfortable right now?"\n\n'

    if openness < 0.4:
        suggestions += "**🚪 Encourage Openness:**\n"
        suggestions += '- "I\'m curious to hear more about that, if you\'re comfortable sharing."\n'
        suggestions += '- "What does a typical day look like for you?"\n'
        suggestions += '- "Tell me about something you enjoy doing."\n\n'

    # Therapeutic technique suggestions
    suggestions += "**🎯 Therapeutic Techniques:**\n"
    suggestions += '- **Validation:** "That sounds really challenging. How has this been affecting you?"\n'
    suggestions += '- **Open Question:** "Can you tell me more about...?"\n'
    suggestions += '- **Reflection:** "It sounds like you\'re feeling... Is that right?"\n'
    suggestions += '- **Explore Meaning:** "What does that mean to you?"\n'

    return suggestions

# Download session transcript
def download_session(conversation_history, state_history, selected_persona_file):
    """Generate downloadable transcript file."""
    if not conversation_history:
        return None
    
    try:
        persona_path = os.path.join(persona_dir, selected_persona_file)
        persona = load_persona(persona_path)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        name = persona.get("persona_name", "Client")
        
        # Create transcript - ONE f-string
        transcript = f"""
================================================================
        OT MENTAL HEALTH SIMULATION - SESSION TRANSCRIPT
================================================================

Client: {name}
Date: {timestamp}
Number of Interactions: {len(conversation_history)}

================================================================
        CONVERSATION
================================================================

"""
        
        for i, turn in enumerate(conversation_history, 1):
            transcript += f"\n[Turn {i}]\n"
            if 'scenario' in turn:
                transcript += f"Context: {turn['scenario']}\n\n"
            transcript += f"Student: {turn.get('student', '')}\n\n"
            transcript += f"{name}: {turn.get('client', '')}\n\n"
            transcript += "-" * 63 + "\n"
        
        if state_history:
            transcript += f"""
================================================================
EMOTIONAL STATE PROGRESSION
================================================================

Initial State:
  Anxiety: {state_history[0].get('anxiety', 0):.2f}
  Trust: {state_history[0].get('trust', 0):.2f}
  Openness: {state_history[0].get('openness', 0):.2f}

Final State:
  Anxiety: {state_history[-1].get('anxiety', 0):.2f}
  Trust: {state_history[-1].get('trust', 0):.2f}
  Openness: {state_history[-1].get('openness', 0):.2f}

Change:
  Anxiety: {state_history[-1].get('anxiety', 0) - state_history[0].get('anxiety', 0):+.2f}
  Trust: {state_history[-1].get('trust', 0) - state_history[0].get('trust', 0):+.2f}
  Openness: {state_history[-1].get('openness', 0) - state_history[0].get('openness', 0):+.2f}

================================================================
"""
        
        # Save to temporary file
        filename = f"{name}_{timestamp}.txt"
        filepath = os.path.join("transcripts", filename)
        os.makedirs("transcripts", exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(transcript)
        
        return filepath
        
    except Exception as e:
        safe_log("Download error", str(e))
        return None

# Main simulation function
def simulate(prompt, selected_event, selected_persona_file, ai_mode, conversation_history, state_history):
    try:
        if hasattr(prompt, 'value'):
            prompt = prompt.value
        prompt = str(prompt) if prompt else ""
        
        if hasattr(selected_event, 'value'):
            selected_event = selected_event.value
        
        if hasattr(selected_persona_file, 'value'):
            selected_persona_file = selected_persona_file.value
            
        if hasattr(ai_mode, 'value'):
            ai_mode = ai_mode.value
            
        persona_path = os.path.join(persona_dir, selected_persona_file)
        persona = load_persona(persona_path)

        response, updated_state, teaching_note = generate_response(
            prompt, 
            persona, 
            conversation_history,
            force_mode=ai_mode  # NEW PARAMETER
        )

        
            
        # Convert Textbox to string if needed
        if not isinstance(prompt, str):
            prompt = str(prompt) if hasattr(prompt, '__str__') else ""
            
        # Parse conversation history
        if conversation_history is None:
            conversation_history = []
        if state_history is None:
            state_history = []

        # Load and apply contextual scenario
        with open(contexts_path, "r") as f:
            scenarios = json.load(f)
        scenario = next((s for s in scenarios if s["scenario"] == selected_event), None)

        if scenario:
            persona = apply_context_shift(persona, scenario)
            context_note = f"**Context:** {scenario.get('description', selected_event)}\n\n"
        else:
            context_note = ""

        # Generate response
        #response, updated_state, teaching_note = generate_response(
         #   student_prompt, 
        #    persona, 
         #   conversation_history
       # )
        
        # Update conversation history
        conversation_history.append({
            "student": prompt,
            "client": response,
            "scenario": selected_event
        })
        
        # Track state history
        state_history.append(updated_state.copy())
        
        # Helper function to get emotional badge
        def get_emotion_badge(value, metric_name):
            if value >= 0.7:
                level = "high"
                emoji = "🔴" if metric_name == "Anxiety" else "🟢"
            elif value >= 0.4:
                level = "medium"
                emoji = "🟡"
            else:
                level = "low"
                emoji = "🟢" if metric_name == "Anxiety" else "🔴"

            return f'<span class="emotion-badge emotion-{level}">{emoji} {metric_name}: {value:.2f}</span>'

        # Format conversation display with chat bubbles (HTML for gr.HTML component)
        conversation_display = f"<h2 style='color: #1e293b; margin-bottom: 20px;'>💬 Session with {persona['persona_name']}</h2>"

        for i, turn in enumerate(conversation_history, 1):
            if 'scenario' in turn and turn['scenario']:
                # Load full scenario description
                try:
                    with open(contexts_path, "r") as f:
                        scenarios = json.load(f)
                    scenario_obj = next((s for s in scenarios if s["scenario"] == turn["scenario"]), None)

                    if scenario_obj:
                        desc = scenario_obj.get("description", turn["scenario"])
                        effects_str = ""
                        if "effects" in scenario_obj:
                            effects = scenario_obj["effects"]
                            if effects:
                                parts = []
                                for key, val in effects.items():
                                    if val > 0:
                                        parts.append(f"↑ {key.replace('_', ' ').title()}")
                                    elif val < 0:
                                        parts.append(f"↓ {key.replace('_', ' ').title()}")
                                effects_str = f" <span class='scenario-effects'>({', '.join(parts)})</span>" if parts else ""

                        conversation_display += f'<div class="scenario-tag">📍 <strong>Situation:</strong> {desc}{effects_str}</div>\n\n'
                    else:
                        conversation_display += f'<div class="scenario-tag">📍 Context: {turn["scenario"]}</div>\n\n'
                except Exception:
                    conversation_display += f'<div class="scenario-tag">📍 Context: {turn["scenario"]}</div>\n\n'

            # Student message (right-aligned blue bubble)
            conversation_display += f'<div class="message-student">\n'
            conversation_display += f'<div class="message-label">👤 You (OT Student)</div>\n'
            conversation_display += f'<div class="message-text">{turn.get("student", "")}</div>\n'
            conversation_display += f'</div>\n\n'

            # Client message with emotional state (left-aligned white bubble)
            conversation_display += f'<div class="message-client">\n'
            conversation_display += f'<div class="message-label">🗣️ {persona["persona_name"]}</div>\n'
            conversation_display += f'<div class="message-text">{turn.get("client", "")}</div>\n'
            conversation_display += f'</div>\n\n'

        # Add current emotional state badges at the end
        if updated_state:
            conversation_display += "<hr style='margin: 20px 0; border: none; border-top: 2px solid #e2e8f0;'>"
            conversation_display += "<h3 style='color: #1e293b; margin: 16px 0;'>Current Emotional State</h3>"
            conversation_display += "<div style='margin: 12px 0;'>"
            conversation_display += get_emotion_badge(updated_state.get('anxiety', 0), 'Anxiety') + " "
            conversation_display += get_emotion_badge(updated_state.get('trust', 0), 'Trust') + " "
            conversation_display += get_emotion_badge(updated_state.get('openness', 0), 'Openness')
            conversation_display += "</div>"
        
        # Generate visualizations
        state_yaml = yaml.dump(updated_state, sort_keys=False)
        current_chart = plot_state(updated_state, persona['persona_name'])
        history_chart = plot_interaction_history(state_history)
        
        # Format teaching feedback with enhanced styling
        teaching_feedback = '<div class="teaching-section">\n'
        teaching_feedback += f'<div class="teaching-title">💡 Teaching Insights</div>\n'
        teaching_feedback += f'{teaching_note}\n'
        teaching_feedback += '</div>\n\n'

        # Add scenario context if present
        if scenario and scenario.get("description"):
            teaching_feedback += '<div style="margin-top: 16px; color: #1e293b;">\n'
            teaching_feedback += '<h3 style="color: #1e293b; margin: 12px 0 8px 0; font-size: 1.1rem;">📍 Session Context</h3>\n'
            teaching_feedback += f'<p style="color: #1e293b; margin: 8px 0;"><strong>Current Situation:</strong> {scenario.get("description")}</p>\n'
            if scenario.get("effects"):
                teaching_feedback += '<p style="color: #1e293b; margin: 8px 0;"><strong>Expected Impact:</strong> '
                effect_parts = []
                for key, val in scenario["effects"].items():
                    arrow = "📈" if val > 0 else "📉"
                    effect_parts.append(f'{arrow} {key.replace("_", " ").title()} ({val:+.2f})')
                teaching_feedback += ', '.join(effect_parts) + '</p>\n'
            teaching_feedback += '</div>\n\n'

        # Session statistics
        num_turns = len(conversation_history)
        initial_anxiety = state_history[0].get('anxiety', 0) if state_history else 0
        current_anxiety = updated_state.get('anxiety', 0)
        anxiety_change = current_anxiety - initial_anxiety

        initial_trust = state_history[0].get('trust', 0) if state_history else 0
        current_trust = updated_state.get('trust', 0)
        trust_change = current_trust - initial_trust

        teaching_feedback += '<div style="margin-top: 16px; color: #1e293b;">\n'
        teaching_feedback += '<h3 style="color: #1e293b; margin: 12px 0 8px 0; font-size: 1.1rem;">📊 Session Statistics</h3>\n'
        teaching_feedback += f'<p style="color: #1e293b; margin: 8px 0;"><strong>Conversation Turns:</strong> {num_turns}</p>\n'

        # Emotional trajectory
        teaching_feedback += '<p style="color: #1e293b; margin: 8px 0;"><strong>Emotional Changes:</strong></p>\n'
        anxiety_arrow = "📈" if anxiety_change > 0 else "📉" if anxiety_change < 0 else "➡️"
        trust_arrow = "📈" if trust_change > 0 else "📉" if trust_change < 0 else "➡️"

        teaching_feedback += '<ul style="color: #1e293b; margin: 8px 0 8px 20px;">\n'
        teaching_feedback += f'<li>Anxiety: {initial_anxiety:.2f} → {current_anxiety:.2f} {anxiety_arrow} ({anxiety_change:+.2f})</li>\n'
        teaching_feedback += f'<li>Trust: {initial_trust:.2f} → {current_trust:.2f} {trust_arrow} ({trust_change:+.2f})</li>\n'
        teaching_feedback += '</ul>\n'

        # Therapeutic relationship assessment
        if current_trust >= 0.7:
            relationship_status = "🟢 <strong>Strong therapeutic alliance</strong>"
        elif current_trust >= 0.5:
            relationship_status = "🟡 <strong>Building trust</strong>"
        elif current_trust >= 0.3:
            relationship_status = "🟠 <strong>Tentative connection</strong>"
        else:
            relationship_status = "🔴 <strong>Trust needs development</strong>"

        teaching_feedback += f'<p style="color: #1e293b; margin: 8px 0;"><strong>Therapeutic Relationship:</strong> {relationship_status}</p>\n'
        teaching_feedback += '</div>\n\n'

        if 'emotional_memory' in updated_state and updated_state['emotional_memory']:
            teaching_feedback += '<div style="margin-top: 16px; color: #1e293b;">\n'
            teaching_feedback += f'<p style="color: #1e293b; margin: 8px 0;"><strong>Recent Emotional Experience:</strong> {updated_state["emotional_memory"][-1]}</p>\n'
            teaching_feedback += '</div>\n'
        
        # Log interaction
        transcript_path = log_interaction(
            persona, 
            prompt, 
            selected_event, 
            response, 
            updated_state,
            teaching_note
        )
        
        return (
            conversation_display,
            teaching_feedback,
            state_yaml,
            current_chart,
            history_chart,
            conversation_history,
            state_history
        )

    except Exception as e:
        error_msg = traceback.format_exc()
        safe_log("Simulation error", error_msg)
        print(f"ERROR: {error_msg}")  # Add this to see in console
        return (
            "[ERROR] Simulation failed. Check logs.", 
            "Error occurred",
            "", 
            None, 
            None,
            conversation_history,
            state_history
        )
# Audio features disabled (not functional)
# def speech_to_text(audio_file):
#     recognizer = sr.Recognizer()
#     with sr.AudioFile(audio_file) as source:
#         audio = recognizer.record(source)
#     try:
#         text = recognizer.recognize_google(audio)
#     except sr.UnknownValueError:
#         text = ""
#     return text

# def simulate_with_voice(audio_in, scenario, persona, mode, conversation_state, state_history):
#     student_prompt = speech_to_text(audio_in) if audio_in else ""
#     conversation_display, teaching_feedback, state_yaml, current_chart, history_chart, conversation_state, state_history = simulate(
#         student_prompt, scenario, persona, mode, conversation_state, state_history
#     )
#     persona_response = conversation_display
#     tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     tts_model.tts_to_file(text=persona_response, file_path=tmpfile.name)
#     return (
#         conversation_display,
#         teaching_feedback,
#         state_yaml,
#         current_chart,
#         history_chart,
#         conversation_state,
#         state_history,
#         tmpfile.name
#     )


# Gradio UI
custom_css = """
.emotion-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 0.875rem;
  font-weight: 600;
  margin: 4px;
}

.emotion-high {
  background-color: #fee2e2;
  color: #991b1b;
}

.emotion-medium {
  background-color: #fef3c7;
  color: #92400e;
}

.emotion-low {
  background-color: #d1fae5;
  color: #065f46;
}

/* Chat bubble styles */
.message-student {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border-radius: 18px 18px 4px 18px;
  padding: 12px 16px;
  margin: 8px 0 8px auto;
  max-width: 80%;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border-left: 4px solid #2563eb;
  color: #1e293b !important;
}

.message-student * {
  color: #1e293b !important;
}

.message-client {
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border-radius: 18px 18px 18px 4px;
  padding: 12px 16px;
  margin: 8px auto 8px 0;
  max-width: 80%;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border-left: 4px solid #f59e0b;
  color: #1e293b !important;
}

.message-client * {
  color: #1e293b !important;
}

.message-label {
  font-weight: 700;
  font-size: 0.875rem;
  margin-bottom: 4px;
  color: #1e293b !important;
}

.message-text {
  line-height: 1.6;
  color: #1e293b !important;
}

/* Persona cards */
.persona-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin: 8px 0;
  border: 2px solid #e2e8f0;
  transition: all 0.3s ease;
  cursor: pointer;
}

.persona-card:hover {
  border-color: #2563eb;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  transform: translateY(-4px);
}

.persona-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  margin-right: 6px;
}

.badge-age {
  background-color: #e0e7ff;
  color: #3730a3;
}

.badge-condition {
  background-color: #fce7f3;
  color: #9f1239;
}

.badge-occupation {
  background-color: #d1fae5;
  color: #065f46;
}

/* Progress indicators */
.progress-bar {
  height: 8px;
  background-color: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
  margin: 8px 0;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb 0%, #10b981 100%);
  transition: width 0.5s ease;
  border-radius: 4px;
}

/* Stats display */
.stat-card {
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  border: 1px solid #e2e8f0;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: #2563eb;
  line-height: 1;
}

.stat-label {
  font-size: 0.875rem;
  color: #64748b;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Teaching feedback enhancements */
.teaching-section {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-left: 4px solid #f59e0b;
  border-radius: 8px;
  padding: 16px;
  margin: 12px 0;
  color: #1e293b !important;
}

.teaching-section * {
  color: #1e293b !important;
}

.teaching-title {
  font-weight: 700;
  color: #92400e !important;
  font-size: 1.1rem;
  margin-bottom: 8px;
}

/* Ensure all teaching feedback text is dark */
[label*="Teaching"] *,
[label="Teaching Feedback"] *,
div:has(> .teaching-section) * {
  color: #1e293b !important;
}

/* Scenario tags */
.scenario-tag {
  display: block;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 0.875rem;
  margin: 8px 0 12px 0;
  border: 1px solid #f59e0b;
  border-left: 4px solid #f59e0b;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  color: #1e293b !important;
}

.scenario-tag strong {
  color: #f59e0b;
  font-weight: 700;
}

.scenario-effects {
  font-size: 0.75rem;
  color: #92400e !important;
  font-weight: 500;
  margin-left: 8px;
  font-style: italic;
}

/* Animations */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-in {
  animation: fadeIn 0.3s ease-out;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  #header-bar {
    flex-direction: column;
    text-align: center;
  }

  .message-student, .message-client {
    max-width: 95%;
  }
}
"""

custom_theme = gr.themes.Default(
    primary_hue="blue",
    secondary_hue="green",
)

with gr.Blocks(
    title="OT Mental Health Simulator",
    theme=custom_theme,
    css=custom_css,
    head="""
    <link rel="manifest" href="/file=manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="OT Simulator">
    <link rel="apple-touch-icon" href="/file=empirenexus.png">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#667eea">
    """
) as ui:

    # Modern Hero Header
    gr.HTML(
        """
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            padding: 40px 24px;
            border-radius: 16px;
            margin-bottom: 24px;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
            position: relative;
            overflow: hidden;">

    <!-- Animated background elements -->
    <div style="position: absolute; top: -50px; right: -50px; width: 200px; height: 200px;
                background: rgba(255,255,255,0.1); border-radius: 50%; opacity: 0.5;"></div>
    <div style="position: absolute; bottom: -30px; left: -30px; width: 150px; height: 150px;
                background: rgba(255,255,255,0.1); border-radius: 50%; opacity: 0.5;"></div>

    <div style="position: relative; z-index: 1;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
            <div>
                <h1 style="color: white; margin: 0; font-size: 2.2em; font-weight: 800;
                           text-shadow: 0 2px 10px rgba(0,0,0,0.2);">
                    🧠 OT Mental Health Simulator
                </h1>
                <p style="color: rgba(255,255,255,0.95); margin: 8px 0 0 0; font-size: 1.15em; font-weight: 500;">
                    Practice real conversations. Build real skills. Make a real impact.
                </p>
            </div>
        </div>

        <!-- Quick Stats Cards -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 12px; margin-top: 24px;">

            <div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(10px);
                        border-radius: 12px; padding: 16px; border: 1px solid rgba(255,255,255,0.3);">
                <div style="font-size: 2em; margin-bottom: 8px;">👥</div>
                <div style="color: white; font-weight: 700; font-size: 1.3em;">8 Personas</div>
                <div style="color: rgba(255,255,255,0.9); font-size: 0.85em;">Diverse, realistic clients</div>
            </div>

            <div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(10px);
                        border-radius: 12px; padding: 16px; border: 1px solid rgba(255,255,255,0.3);">
                <div style="font-size: 2em; margin-bottom: 8px;">🎭</div>
                <div style="color: white; font-weight: 700; font-size: 1.3em;">19 Scenarios</div>
                <div style="color: rgba(255,255,255,0.9); font-size: 0.85em;">Real-world situations</div>
            </div>

            <div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(10px);
                        border-radius: 12px; padding: 16px; border: 1px solid rgba(255,255,255,0.3);">
                <div style="font-size: 2em; margin-bottom: 8px;">🤖</div>
                <div style="color: white; font-weight: 700; font-size: 1.3em;">AI-Powered</div>
                <div style="color: rgba(255,255,255,0.9); font-size: 0.85em;">Fast, private responses</div>
            </div>

            <div style="background: rgba(255,255,255,0.2); backdrop-filter: blur(10px);
                        border-radius: 12px; padding: 16px; border: 1px solid rgba(255,255,255,0.3);">
                <div style="font-size: 2em; margin-bottom: 8px;">📊</div>
                <div style="color: white; font-weight: 700; font-size: 1.3em;">Live Feedback</div>
                <div style="color: rgba(255,255,255,0.9); font-size: 0.85em;">Track emotional impact</div>
            </div>
        </div>
    </div>
</div>
"""
    )

    # Skills showcase - modern cards
    gr.HTML(
        """
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px; margin-bottom: 24px;">

    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px; padding: 20px; color: white;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
                transition: transform 0.2s;">
        <div style="font-size: 1.8em; margin-bottom: 8px;">🤝</div>
        <h4 style="margin: 0 0 8px 0; font-size: 1.1em;">Build Rapport</h4>
        <p style="margin: 0; font-size: 0.9em; opacity: 0.95;">Develop therapeutic relationships through authentic communication</p>
    </div>

    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                border-radius: 12px; padding: 20px; color: white;
                box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3);">
        <div style="font-size: 1.8em; margin-bottom: 8px;">👂</div>
        <h4 style="margin: 0 0 8px 0; font-size: 1.1em;">Active Listening</h4>
        <p style="margin: 0; font-size: 0.9em; opacity: 0.95;">Practice validation and empathetic responses</p>
    </div>

    <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                border-radius: 12px; padding: 20px; color: white;
                box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3);">
        <div style="font-size: 1.8em; margin-bottom: 8px;">🎯</div>
        <h4 style="margin: 0 0 8px 0; font-size: 1.1em;">Recognize Triggers</h4>
        <p style="margin: 0; font-size: 0.9em; opacity: 0.95;">Identify emotional states and adjust your approach</p>
    </div>

    <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
                border-radius: 12px; padding: 20px; color: white;
                box-shadow: 0 4px 15px rgba(67, 233, 123, 0.3);">
        <div style="font-size: 1.8em; margin-bottom: 8px;">💪</div>
        <h4 style="margin: 0 0 8px 0; font-size: 1.1em;">Occupational Focus</h4>
        <p style="margin: 0; font-size: 0.9em; opacity: 0.95;">Understand how mental health impacts daily activities</p>
    </div>
</div>
"""
    )

    # State management
    conversation_state = gr.State([])
    state_history = gr.State([])

    # Quick Start Guide
    gr.HTML(
        """
<div style="background: white;
            border-radius: 12px; padding: 20px; margin-bottom: 24px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <h3 style="color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; font-weight: 700;">
        🚀 <span style="margin-left: 8px;">Quick Start Guide</span>
    </h3>
    <div style="color: #1e293b; line-height: 1.7; font-size: 0.95em;">
        <div style="margin: 10px 0; display: flex; align-items: start;">
            <span style="background: #667eea; color: white; border-radius: 50%;
                         width: 28px; height: 28px; display: inline-flex; align-items: center;
                         justify-content: center; font-weight: 700; margin-right: 12px; flex-shrink: 0; font-size: 0.9em;">1</span>
            <span style="color: #1e293b;"><strong style="color: #1e293b;">Choose a client</strong> from the dropdown below</span>
        </div>
        <div style="margin: 10px 0; display: flex; align-items: start;">
            <span style="background: #764ba2; color: white; border-radius: 50%;
                         width: 28px; height: 28px; display: inline-flex; align-items: center;
                         justify-content: center; font-weight: 700; margin-right: 12px; flex-shrink: 0; font-size: 0.9em;">2</span>
            <span style="color: #1e293b;"><strong style="color: #1e293b;">Select a scenario</strong> that sets the context</span>
        </div>
        <div style="margin: 10px 0; display: flex; align-items: start;">
            <span style="background: #f093fb; color: white; border-radius: 50%;
                         width: 28px; height: 28px; display: inline-flex; align-items: center;
                         justify-content: center; font-weight: 700; margin-right: 12px; flex-shrink: 0; font-size: 0.9em;">3</span>
            <span style="color: #1e293b;"><strong style="color: #1e293b;">Start the conversation</strong> and watch emotions shift!</span>
        </div>
    </div>
</div>
"""
    )

    # Main row: left column (selectors + info + mode) and right column (conversation)
    with gr.Row():
        with gr.Column(scale=1):
            # Client Selection Section
            gr.HTML('<h3 style="color: #667eea; margin: 0 0 12px 0; display: flex; align-items: center;"><span style="font-size: 1.3em; margin-right: 8px;">👥</span> Choose Your Client</h3>')

            persona_files = get_persona_choices()
            default_persona = persona_files[0] if persona_files else None

            persona_selector = gr.Dropdown(
                label="",
                choices=persona_files,
                value=default_persona,
                allow_custom_value=False,
                info="Select which client you'll be working with today"
            )

            gr.HTML('<div style="height: 20px;"></div>')  # Spacer

            # Scenario Selection Section
            gr.HTML('<h3 style="color: #764ba2; margin: 0 0 12px 0; display: flex; align-items: center;"><span style="font-size: 1.3em; margin-right: 8px;">🎭</span> Set the Scene</h3>')

            scenario_choices = get_scenario_choices()
            scenario_selector = gr.Dropdown(
                label="",
                choices=scenario_choices,
                value=scenario_choices[0] if scenario_choices else None,
                info="What's happening in the client's life right now?"
            )

            gr.HTML('<hr style="margin: 24px 0; border: none; border-top: 2px solid #e2e8f0;">')

            with gr.Accordion("📋 Meet the Clients", open=False):
                gr.HTML(
"""
<div style="padding: 8px;">

<div style="background: linear-gradient(135deg, #dbeafe 0%, #e0e7ff 100%); border-left: 4px solid #667eea;
            border-radius: 8px; padding: 12px; margin: 8px 0; color: #1e293b;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 1.5em; margin-right: 8px;">🏗️</span>
        <strong style="font-size: 1.05em;">Jack, 22</strong>
        <span style="background: #667eea; color: white; font-size: 0.7em; padding: 2px 8px;
                     border-radius: 12px; margin-left: 8px;">Construction Worker</span>
    </div>
    <p style="margin: 4px 0; font-size: 0.9em; line-height: 1.5;">
        Aspiring streamer navigating chronic knee pain, family dynamics, gaming as escape vs. passion, and identity questions.
    </p>
</div>

<div style="background: linear-gradient(135deg, #fce7f3 0%, #fef3c7 100%); border-left: 4px solid #f093fb;
            border-radius: 8px; padding: 12px; margin: 8px 0; color: #1e293b;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 1.5em; margin-right: 8px;">🎨</span>
        <strong style="font-size: 1.05em;">Maya, 24</strong>
        <span style="background: #f093fb; color: white; font-size: 0.7em; padding: 2px 8px;
                     border-radius: 12px; margin-left: 8px;">Graphic Designer</span>
    </div>
    <p style="margin: 4px 0; font-size: 0.9em; line-height: 1.5;">
        Experiencing creative burnout, work-life imbalance, anxiety, imposter syndrome, and physical symptoms from chronic overwork.
    </p>
</div>

<div style="background: linear-gradient(135deg, #e0e7ff 0%, #ddd6fe 100%); border-left: 4px solid #764ba2;
            border-radius: 8px; padding: 12px; margin: 8px 0; color: #1e293b;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 1.5em; margin-right: 8px;">💼</span>
        <strong style="font-size: 1.05em;">Robert, 60</strong>
        <span style="background: #764ba2; color: white; font-size: 0.7em; padding: 2px 8px;
                     border-radius: 12px; margin-left: 8px;">Office Administrator</span>
    </div>
    <p style="margin: 4px 0; font-size: 0.9em; line-height: 1.5;">
        Facing retirement transition, loss of work identity, adapting to workplace technology changes, and questions of purpose.
    </p>
</div>

<div style="background: linear-gradient(135deg, #fed7aa 0%, #fef3c7 100%); border-left: 4px solid #f59e0b;
            border-radius: 8px; padding: 12px; margin: 8px 0; color: #1e293b;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 1.5em; margin-right: 8px;">🏪</span>
        <strong style="font-size: 1.05em;">Angela, 45</strong>
        <span style="background: #f59e0b; color: white; font-size: 0.7em; padding: 2px 8px;
                     border-radius: 12px; margin-left: 8px;">Retail Manager</span>
    </div>
    <p style="margin: 4px 0; font-size: 0.9em; line-height: 1.5;">
        Balancing chronic lower back pain, single parenting a teenage son, financial stress, and loss of meaningful leisure activities.
    </p>
</div>

<div style="background: linear-gradient(135deg, #fecaca 0%, #fed7aa 100%); border-left: 4px solid #f5576c;
            border-radius: 8px; padding: 12px; margin: 8px 0; color: #1e293b;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 1.5em; margin-right: 8px;">📚</span>
        <strong style="font-size: 1.05em;">Sofia, 28</strong>
        <span style="background: #f5576c; color: white; font-size: 0.7em; padding: 2px 8px;
                     border-radius: 12px; margin-left: 8px;">ESL Teacher</span>
    </div>
    <p style="margin: 4px 0; font-size: 0.9em; line-height: 1.5;">
        Recent immigrant from Colombia navigating cultural displacement, homesickness, professional credential barriers, and identity between two worlds.
    </p>
</div>

<div style="background: linear-gradient(135deg, #d1fae5 0%, #dbeafe 100%); border-left: 4px solid #10b981;
            border-radius: 8px; padding: 12px; margin: 8px 0; color: #1e293b;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 1.5em; margin-right: 8px;">🪖</span>
        <strong style="font-size: 1.05em;">Devon, 35</strong>
        <span style="background: #10b981; color: white; font-size: 0.7em; padding: 2px 8px;
                     border-radius: 12px; margin-left: 8px;">Veteran/Security</span>
    </div>
    <p style="margin: 4px 0; font-size: 0.9em; line-height: 1.5;">
        Military veteran (Army, 2 Afghanistan tours) with PTSD and TBI, struggling with hypervigilance and civilian transition.
    </p>
</div>

<div style="background: linear-gradient(135deg, #e0f2fe 0%, #ddd6fe 100%); border-left: 4px solid #4facfe;
            border-radius: 8px; padding: 12px; margin: 8px 0; color: #1e293b;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 1.5em; margin-right: 8px;">🏥</span>
        <strong style="font-size: 1.05em;">Priya, 42</strong>
        <span style="background: #4facfe; color: white; font-size: 0.7em; padding: 2px 8px;
                     border-radius: 12px; margin-left: 8px;">ICU Nurse</span>
    </div>
    <p style="margin: 4px 0; font-size: 0.9em; line-height: 1.5;">
        Working night shifts while caring for mother with Alzheimer's, experiencing caregiver burden and complete physical/emotional depletion.
    </p>
</div>

<div style="background: linear-gradient(135deg, #fef3c7 0%, #dbeafe 100%); border-left: 4px solid #43e97b;
            border-radius: 8px; padding: 12px; margin: 8px 0; color: #1e293b;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 1.5em; margin-right: 8px;">🎓</span>
        <strong style="font-size: 1.05em;">Marcus, 19</strong>
        <span style="background: #43e97b; color: white; font-size: 0.7em; padding: 2px 8px;
                     border-radius: 12px; margin-left: 8px;">College Freshman</span>
    </div>
    <p style="margin: 4px 0; font-size: 0.9em; line-height: 1.5;">
        With ADHD struggling with executive dysfunction, academic probation, inconsistent medication adherence, and feeling like he's failing.
    </p>
</div>

<div style="margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: 8px; text-align: center;">
    <p style="color: #64748b; font-style: italic; margin: 0; font-size: 0.85em;">
        ✨ Each persona features rich psychological depth, realistic triggers, and authentic communication patterns
    </p>
</div>

</div>
"""
                )

            ai_mode_selector = gr.Radio(
                label="Response Mode",
                choices=["AI", "Templates (Local)"],
                value="AI",
                info="AI uses local transformers model (fast), Templates use pre-written responses"
            )

        with gr.Column(scale=2):
            conversation_display = gr.HTML(
                label="Conversation History",
                value="<p style='color: #64748b; font-style: italic; text-align: center; padding: 40px;'>Conversation will appear here...</p>"
            )

    # Audio features disabled (not functional)
    # with gr.Row():
    #     audio_in = gr.Audio(type="filepath", label="🎤 Speak to the client", interactive=True)
    #     voice_submit_btn = gr.Button("Send Voice Input")
    #     audio_out = gr.Audio(label="Persona Voice", type="filepath")


    # Student input row with suggestions
    with gr.Row():
        with gr.Column():
            student_prompt = gr.Textbox(
                label="Your Response (as OT student/practitioner)",
                lines=3,
                placeholder="Start with: 'Hi, I'm [your name], an OT student...' or just say hello",
                value=""
            )

    # Smart suggestions section
    with gr.Row():
        with gr.Column():
            with gr.Accordion("💡 Smart Response Suggestions", open=False):
                suggestions_display = gr.Markdown(
                    value="### Select a client and start a conversation to see suggestions",
                    label="Suggestions"
                )
                get_suggestions_btn = gr.Button("🔄 Refresh Suggestions", size="sm")

    # Buttons row
    with gr.Row():
        with gr.Column(scale=1):
            send_btn = gr.Button("Send Response", variant="primary", size="lg")
        with gr.Column(scale=1):
            download_btn = gr.Button("Download Session", size="lg")
        with gr.Column(scale=1):
            reset_btn = gr.Button("Reset Conversation", size="lg")

    # Teaching feedback + technical state row
    with gr.Row():
        with gr.Column():
            teaching_output = gr.HTML(label="Teaching Feedback")
        with gr.Column():
            state_output = gr.Textbox(
                label="Technical State (for debugging)",
                lines=8,
                visible=False  # Hide by default, can be toggled
            )

    # Charts row
    with gr.Row():
        with gr.Column():
            current_state_chart = gr.Image(label="Current Emotional State")
        with gr.Column():
            history_chart = gr.Image(label="Progress Over Time")

    # Hidden file output for downloads
    download_file = gr.File(
        label="Your session transcript (right-click to save)",
        visible=True
    )

    # Instructor guide
    with gr.Accordion("Instructor Guide", open=False):
        gr.Markdown(
            """




### How to Use This Simulator

1. **Select a client** (Jack or Maya)
2. **Choose a scenario** to set the context
3. **Type your therapeutic response** as if you were the OT practitioner
4. **Observe** how the client responds based on:
   - Their emotional state (anxiety, trust, openness)
   - The scenario context
   - Your communication approach
5. **Review teaching feedback** to understand what worked or didn't
6. **Track progress** through the radar chart and history graph

### Teaching Points
- Notice how validation vs. advice-giving affects trust
- Observe how pacing affects client openness
- See how boundary-setting affects the therapeutic relationship
- Track how emotional states shift with different approaches

### Sample Scenarios to Explore
- Building initial rapport
- Responding to resistance
- Addressing pain and physical symptoms
- Exploring occupational balance
- Managing therapeutic ruptures
- Crisis response
"""
        )

    # Button actions
    send_btn.click(
        fn=simulate,
        inputs=[
            student_prompt,
            scenario_selector,
            persona_selector,
            ai_mode_selector,
            conversation_state,
            state_history
        ],
        outputs=[
            conversation_display,
            teaching_output,
            state_output,
            current_state_chart,
            history_chart,
            conversation_state,
            state_history
        ]
    )

    download_btn.click(
        fn=download_session,
        inputs=[
            conversation_state,
            state_history,
            persona_selector
        ],
        outputs=download_file
    )

    get_suggestions_btn.click(
        fn=generate_suggestions,
        inputs=[
            conversation_state,
            state_history,
            persona_selector
        ],
        outputs=suggestions_display
    )
    # Audio features disabled (not functional)
    # voice_submit_btn.click(
    #     fn=simulate_with_voice,
    #     inputs=[
    #         audio_in,
    #         scenario_selector,
    #         persona_selector,
    #         ai_mode_selector,
    #         conversation_state,
    #         state_history
    #     ],
    #     outputs=[
    #         conversation_display,
    #         teaching_output,
    #         state_output,
    #         current_state_chart,
    #         history_chart,
    #         conversation_state,
    #         state_history,
    #         audio_out
    #     ]
    # )
    def reset_conversation():
        return (
            "<p style='color: #64748b; font-style: italic; text-align: center; padding: 40px;'>Conversation will appear here...</p>",
            "",
            "",
            None,
            None,
            [],
            []
        )

    reset_btn.click(
        fn=reset_conversation,
        inputs=[],
        outputs=[
            conversation_display,
            teaching_output,
            state_output,
            current_state_chart,
            history_chart,
            conversation_state,
            state_history
        ]
    )

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("personas", exist_ok=True)
    os.makedirs("contexts", exist_ok=True)
    os.makedirs("transcripts", exist_ok=True)
    os.makedirs("engine", exist_ok=True)

    ui.launch(
        pwa=True,
        favicon_path="empirenexus.png",
        share=False,
        server_name="0.0.0.0",
        server_port=7860
    )