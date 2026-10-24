# Running the Claude benchmark (Q4) on your laptop

Everything else in the paper is already computed. This step needs a real model, so it runs on your
machine with your own Anthropic API key. Your key never leaves your computer.

## 1. One-time setup (Windows, PowerShell)
1. Install Python 3.11 or newer from python.org (tick "Add python.exe to PATH").
2. Unzip `capscope.zip` (or `git clone` the repo) and open PowerShell in the folder.
3. Install the exact versions used in the paper:
   ```
   pip install -r code/requirements.txt
   ```
4. In the Anthropic Console (console.anthropic.com): create an API key, and under **Limits** set a
   monthly spend limit (e.g. $40) so a mistake can never cost more than that.
5. Put the key in your environment (not in any file):
   ```
   setx ANTHROPIC_API_KEY "paste-your-key-here"
   ```
   Close PowerShell and open a new one so the key is loaded.

## 2. Check that everything works, for free
```
cd code
python run_llm.py --dry-run --pilot --suite banking
```
This uses a fake offline model. It should print `[banking] benign utility ...` and `written ...`.

## 3. Pilot: measure the real cost (about 30 episodes)
```
python run_llm.py --defense none --suite banking --pilot
```
At the end it prints **"Estimate for a FULL run of this defense: ~X M input and ~Y M output tokens"**.
Multiply by the model's price on anthropic.com/pricing. Send me that line before going further if the
total for three defenses is above your budget; we can then run a subset (e.g. the 629 v1 pairs only).

## 4. Full runs (one after another, each takes a few hours)
```
python run_llm.py --defense none
python run_llm.py --defense capscope
python run_llm.py --defense tool_filter
```
If your internet drops or the laptop sleeps, just run the same command again: finished episodes are
skipped. (If you had to restart, tell me, because the token and time counts then cover only the last part.)

## 5. Send the results back
Zip the whole `runs` folder and upload it in our chat. I will run `analyze_llm.py`, fill in Q4 and
finish the paper.

## Notes
- Model: `claude-haiku-5-5` (change with `--model`). Attack: AgentDojo's `important_instructions`.
- Do not change any code or profile before running; the paper reports the frozen version (see PROTOCOL.md).
