import os
from datetime import datetime
import json
import yaml

def log_interaction(persona, student_prompt, scenario, response, state, teaching_note):
    """
    Log a therapeutic interaction for review and assessment purposes.
    Creates both human-readable and machine-readable formats.
    """
    name = persona.get("persona_name", "Unknown")
    age = persona.get("age", "")
    role = persona.get("role", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Human-readable transcript
    transcript = f"""
╔══════════════════════════════════════════════════════════════╗
║         OT MENTAL HEALTH SIMULATION TRANSCRIPT               ║
╚══════════════════════════════════════════════════════════════╝

Timestamp: {timestamp}
Client: {name} ({age}, {role})
Scenario Context: {scenario}

─────────────────────────────────────────────────────────────

OT STUDENT RESPONSE:
{student_prompt}

─────────────────────────────────────────────────────────────

CLIENT RESPONSE:
{response}

─────────────────────────────────────────────────────────────

EMOTIONAL STATE AFTER INTERACTION:
• Anxiety Level:    {state.get('anxiety', 0):.2f} {'█' * int(state.get('anxiety', 0) * 10)}
• Trust Level:      {state.get('trust', 0):.2f} {'█' * int(state.get('trust', 0) * 10)}
• Openness:         {state.get('openness', 0):.2f} {'█' * int(state.get('openness', 0) * 10)}
• Current Mode:     {state.get('mode', 'baseline')}

{f"• Physical Discomfort: {state.get('physical_discomfort', 0):.2f}" if 'physical_discomfort' in state else ""}
{f"• Creative Engagement: {state.get('creative_engagement', 0):.2f}" if 'creative_engagement' in state else ""}
{f"• Occupational Balance: {state.get('occupational_balance', 0):.2f}" if 'occupational_balance' in state else ""}

─────────────────────────────────────────────────────────────

TEACHING FEEDBACK:
{teaching_note}

─────────────────────────────────────────────────────────────

EMOTIONAL MEMORY:
{format_emotional_memory(state.get('emotional_memory', []))}

═════════════════════════════════════════════════════════════
"""
    
    # Save human-readable transcript
    os.makedirs("transcripts", exist_ok=True)
    safe_name = name.replace(' ', '_')
    safe_timestamp = timestamp.replace(':', '-').replace(' ', '_')
    filename = f"transcripts/{safe_name}_{safe_timestamp}.txt"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(transcript)
    
    # Save machine-readable JSON for analysis
    json_data = {
        "timestamp": timestamp,
        "client": {
            "name": name,
            "age": age,
            "role": role
        },
        "scenario": scenario,
        "interaction": {
            "student_prompt": student_prompt,
            "client_response": response
        },
        "state": state,
        "teaching_note": teaching_note
    }
    
    json_filename = f"transcripts/{safe_name}_{safe_timestamp}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)
    
    return filename


def format_emotional_memory(memory_list):
    """Format emotional memory for display."""
    if not memory_list:
        return "No emotional memories recorded yet."
    
    formatted = ""
    for i, memory in enumerate(memory_list, 1):
        formatted += f"  {i}. {memory}\n"
    return formatted


def log_session_summary(persona, interactions, final_state):
    """
    Log a summary of an entire session (multiple interactions).
    """
    name = persona.get("persona_name", "Unknown")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    summary = f"""
╔══════════════════════════════════════════════════════════════╗
║              SESSION SUMMARY REPORT                          ║
╚══════════════════════════════════════════════════════════════╝

Client: {name}
Date: {timestamp}
Number of Interactions: {len(interactions)}

─────────────────────────────────────────────────────────────

INTERACTION OVERVIEW:
"""
    
    for i, interaction in enumerate(interactions, 1):
        summary += f"""
Turn {i}:
  Student: {interaction.get('student', '')[:80]}...
  Client Mode: {interaction.get('mode', 'unknown')}
  Anxiety: {interaction.get('anxiety', 0):.2f} | Trust: {interaction.get('trust', 0):.2f}
"""
    
    summary += f"""

─────────────────────────────────────────────────────────────

FINAL STATE:
• Anxiety:          {final_state.get('anxiety', 0):.2f}
• Trust:            {final_state.get('trust', 0):.2f}
• Openness:         {final_state.get('openness', 0):.2f}
• Mode:             {final_state.get('mode', 'baseline')}

─────────────────────────────────────────────────────────────

THERAPEUTIC PROGRESS INDICATORS:

Trust Development:    {assess_trust_progress(interactions)}
Anxiety Management:   {assess_anxiety_progress(interactions)}
Openness to Engage:   {assess_openness_progress(interactions)}

─────────────────────────────────────────────────────────────

RECOMMENDATIONS FOR FUTURE SESSIONS:
{generate_recommendations(persona, interactions, final_state)}

═════════════════════════════════════════════════════════════
"""
    
    # Save summary
    os.makedirs("transcripts/summaries", exist_ok=True)
    summary_filename = f"transcripts/summaries/{name.replace(' ', '_')}_{timestamp}.txt"
    
    with open(summary_filename, "w", encoding="utf-8") as f:
        f.write(summary)
    
    return summary_filename


def assess_trust_progress(interactions):
    """Assess how trust developed over the session."""
    if len(interactions) < 2:
        return "Insufficient data"
    
    trust_values = [i.get('trust', 0.5) for i in interactions if 'trust' in i]
    
    if not trust_values:
        return "No trust data available"
    
    initial = trust_values[0]
    final = trust_values[-1]
    change = final - initial
    
    if change > 0.15:
        return f"Strong improvement (+{change:.2f})"
    elif change > 0.05:
        return f"Moderate improvement (+{change:.2f})"
    elif change < -0.15:
        return f"Significant decline ({change:.2f})"
    elif change < -0.05:
        return f"Slight decline ({change:.2f})"
    else:
        return f"Stable ({change:+.2f})"


def assess_anxiety_progress(interactions):
    """Assess how anxiety changed over the session."""
    if len(interactions) < 2:
        return "Insufficient data"
    
    anxiety_values = [i.get('anxiety', 0.5) for i in interactions if 'anxiety' in i]
    
    if not anxiety_values:
        return "No anxiety data available"
    
    initial = anxiety_values[0]
    final = anxiety_values[-1]
    change = final - initial
    
    # Note: For anxiety, decrease is good
    if change < -0.15:
        return f"Significant reduction ({change:.2f}) ✓"
    elif change < -0.05:
        return f"Moderate reduction ({change:.2f}) ✓"
    elif change > 0.15:
        return f"Significant increase (+{change:.2f}) ⚠"
    elif change > 0.05:
        return f"Slight increase (+{change:.2f})"
    else:
        return f"Stable ({change:+.2f})"


def assess_openness_progress(interactions):
    """Assess how openness changed over the session."""
    if len(interactions) < 2:
        return "Insufficient data"
    
    openness_values = [i.get('openness', 0.5) for i in interactions if 'openness' in i]
    
    if not openness_values:
        return "No openness data available"
    
    initial = openness_values[0]
    final = openness_values[-1]
    change = final - initial
    
    if change > 0.15:
        return f"Significant increase (+{change:.2f}) ✓"
    elif change > 0.05:
        return f"Moderate increase (+{change:.2f}) ✓"
    elif change < -0.15:
        return f"Significant decrease ({change:.2f}) ⚠"
    elif change < -0.05:
        return f"Slight decrease ({change:.2f})"
    else:
        return f"Stable ({change:+.2f})"


def generate_recommendations(persona, interactions, final_state):
    """Generate recommendations based on session data."""
    recommendations = []
    
    # Check trust level
    trust = final_state.get('trust', 0.5)
    if trust < 0.4:
        recommendations.append("• Focus on rapport building and validation in next session")
        recommendations.append("• Avoid pushing for deep disclosure too quickly")
    elif trust > 0.7:
        recommendations.append("• Strong therapeutic alliance established")
        recommendations.append("• May be ready for deeper exploration of difficult topics")
    
    # Check anxiety level
    anxiety = final_state.get('anxiety', 0.5)
    if anxiety > 0.7:
        recommendations.append("• Client experiencing high anxiety - prioritize safety and stability")
        recommendations.append("• Consider anxiety management techniques and grounding")
    
    # Check openness
    openness = final_state.get('openness', 0.5)
    if openness < 0.3:
        recommendations.append("• Client is guarded - respect pace and boundaries")
        recommendations.append("• Use more open-ended questions and active listening")
    
    # Mode-specific recommendations
    mode = final_state.get('mode', 'baseline')
    if mode == 'decompensating':
        recommendations.append("• ⚠ CLIENT MAY NEED CRISIS INTERVENTION")
        recommendations.append("• Assess safety and consider referral to mental health services")
    elif mode == 'triggered':
        recommendations.append("• Client ended session in defensive state")
        recommendations.append("• Begin next session with rapport repair")
    
    if not recommendations:
        recommendations.append("• Continue with current therapeutic approach")
        recommendations.append("• Build on positive progress from this session")
    
    return "\n".join(recommendations)


def export_session_for_assessment(persona, interactions, final_state, student_name=""):
    """
    Export session data in a format suitable for instructor assessment.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    name = persona.get("persona_name", "Unknown")
    
    assessment_data = {
        "student_name": student_name,
        "timestamp": timestamp,
        "client": name,
        "interactions": interactions,
        "final_state": final_state,
        "metrics": {
            "trust_progress": assess_trust_progress(interactions),
            "anxiety_progress": assess_anxiety_progress(interactions),
            "openness_progress": assess_openness_progress(interactions)
        },
        "recommendations": generate_recommendations(persona, interactions, final_state)
    }
    
    os.makedirs("transcripts/assessments", exist_ok=True)
    filename = f"transcripts/assessments/{student_name}_{name}_{timestamp}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(assessment_data, f, indent=2)
    
    return filename