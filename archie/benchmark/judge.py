# archie/benchmark/judge.py
import json
import subprocess


def assign_order(seed):
    """Return (treatment_variant, control_variant) — blind A/B label assignment."""
    return ("a", "b") if seed % 2 == 0 else ("b", "a")


def build_judge_prompt(task_prompt, diff_a, diff_b, rubric):
    axes = ", ".join(rubric)
    schema = ('{"variant_a": {' + ", ".join(f'"{a}": int' for a in rubric)
              + ', "overall": number, "justification": string}, "variant_b": {... same keys ...}}')
    return (
        "You are an impartial senior code reviewer. Two AI agents independently "
        "attempted the SAME task. You are shown each agent's diff as an anonymous "
        "variant. Judge purely on the code; you do not know anything about how each "
        "was produced.\n\n"
        f"TASK GIVEN TO BOTH AGENTS:\n{task_prompt}\n\n"
        f"Score each variant on these axes (each 1-10): {axes}. Also give an "
        "'overall' score (0-10) and a one-sentence 'justification'.\n\n"
        f"Respond with ONLY a JSON object of this exact shape:\n{schema}\n\n"
        f"=== VARIANT A DIFF ===\n{diff_a}\n\n"
        f"=== VARIANT B DIFF ===\n{diff_b}\n"
    )


def parse_judge_output(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in judge output")
    return json.loads(text[start:end + 1])


def _default_runner(prompt, model, timeout):
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout,
    )
    return proc.stdout


def run_judge(task_prompt, treatment_diff, control_diff, rubric, model, seed,
              timeout_seconds=600, _runner=None):
    t_variant, c_variant = assign_order(seed)
    diff_a = treatment_diff if t_variant == "a" else control_diff
    diff_b = treatment_diff if t_variant == "b" else control_diff
    prompt = build_judge_prompt(task_prompt, diff_a, diff_b, rubric)

    runner = _runner or _default_runner
    parsed = None
    last_err = None
    for _ in range(2):
        try:
            parsed = parse_judge_output(runner(prompt, model, timeout_seconds))
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
    if parsed is None:
        raise ValueError(f"judge returned unparseable output twice: {last_err}")

    return {
        "treatment": parsed["variant_a"] if t_variant == "a" else parsed["variant_b"],
        "control": parsed["variant_a"] if c_variant == "a" else parsed["variant_b"],
        "seed": seed,
    }
