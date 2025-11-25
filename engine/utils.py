def safe_log(context, error):
    with open("driftline_errors.log", "a", encoding="utf-8") as f:
        f.write(f"[{context}] {error}\n")