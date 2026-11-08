def ingest_research_context() -> tuple:
    """Reads folder data and injects local repository voice configurations."""
    context_chunks = []
    
    # Check if the Voice DNA profile exists locally in the repository root
    voice_profile = Path("./few_shot_voice_examples.md")
    if voice_profile.exists():
        context_chunks.append(f"--- MANDATORY VOICE DNA BLUEPRINT ---\n{voice_profile.read_text()}")
        
    for file_path in RESEARCH_DIR.glob("*.md"):
        try:
            context_chunks.append(f"--- ATTACHED TELEMETRY: {file_path.name} ---\n{file_path.read_text()}")
        except Exception:
            pass
            
    if context_chunks:
        return "\n\n".join(context_chunks), False
    else:
        return "NOTICE: Background research directories empty. Inmode: Zero-Input Autonomous Ideation.", True
