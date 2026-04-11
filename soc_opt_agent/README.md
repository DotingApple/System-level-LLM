# soc_opt_agent

`soc_opt_agent` is a local Python agent for SoC-level optimization of ESP designs.

The current focus is:

- optimize SoC parameters only
- do not modify accelerator RTL
- use ESP monitor outputs from Modelsim
- support a saved baseline plus iterative candidate runs
- allow an LLM policy to propose `.esp_config` changes

Today the project is centered on:

- target SoC: `/home/cz2931/esp/socs/xilinx-vc707-xc7vx485t`
- first accelerator: `aescipher_rtl`
- current LLM backend: Gemini via API key

## What It Does

At a high level, the agent can:

- run and save a per-accelerator baseline
- ask an LLM for a SoC config proposal
- edit `.esp_config` safely within an allowlist
- run `make esp-config`
- build the baremetal benchmark
- run Modelsim
- parse monitor metrics from `modelsim/transcript`
- save run artifacts for later comparison
- run a simple closed loop until plateau

The current optimization signal is based on:

- `Accelerator total cycles`
- `Off-chip memory accesses`
- `PASS/FAIL`

## Quick Start

From the project root:

```bash
cd /home/cz2931/esp/soc_opt_agent
source .venv/bin/activate
```

Set your Gemini key:

```bash
export GEMINI_API_KEY='your_key_here'
```

Check current status:

```bash
agentsoc status
```

Run or reuse the saved baseline for the next accelerator:

```bash
agentsoc baseline
```

Run one LLM-driven candidate iteration:

```bash
agentsoc run_once
```

Run the full loop:

```bash
agentsoc run_all
```

Stop an active `run_all`:

```bash
agentsoc stop
```

You can also use the alias:

```bash
agentrtl status
agentrtl run_all
agentrtl stop
```

Right now `agentrtl` is only an alias for the same backend. It does not yet implement a separate RTL-optimization workflow.

## Common Workflow

Typical first-time workflow:

1. Activate the venv and set `GEMINI_API_KEY`.
2. Run `agentsoc status`.
3. Run `agentsoc baseline`.
4. Inspect the saved baseline under `baselines/<accelerator>/`.
5. Run `agentsoc run_once` for a single candidate.
6. When comfortable, run `agentsoc run_all`.

Typical day-to-day workflow:

```bash
cd /home/cz2931/esp/soc_opt_agent
source .venv/bin/activate
export GEMINI_API_KEY='your_key_here'
agentsoc run_all
```

In another terminal:

```bash
tail -f /home/cz2931/esp/soc_opt_agent/agent_transcript.log
```

## CLI Commands

The preferred interface is the positional subcommand form.

### `agentsoc status`

Shows:

- next accelerator
- completed accelerators from `campaign.yaml`
- queue size
- scoring config
- llm config
- path to `run_all.status.json` when present

### `agentsoc baseline`

Runs the baseline for the next accelerator in queue, unless a saved baseline already exists.

Behavior:

- if baseline exists: reuse it
- if baseline does not exist: run `esp-config -> baremetal -> sim`
- save results under `baselines/<accelerator>/`

### `agentsoc run_once`

Runs one LLM-driven candidate iteration for the next accelerator.

Behavior:

- load current `.esp_config`
- load LLM config
- ask the model for a proposal
- apply changes inside the allowlist
- run `esp-config -> baremetal -> sim`
- save artifacts under `runs/run_*_<accelerator>/`

### `agentsoc run_all`

Runs the simple closed loop.

Current flow:

1. build the accelerator queue
2. load or create baseline
3. run candidate iterations
4. track improvement versus current best
5. stop on plateau
6. move to the next accelerator

Current plateau rule comes from `configs/scoring.yaml`.

### `agentsoc stop`

Stops an active `run_all`.

Current behavior:

- writes the stop marker
- sends termination to the `run_all` process tree

This is intended to stop the active loop quickly, not just after the current iteration finishes.

## Project Layout

```text
soc_opt_agent/
├── README.md
├── pyproject.toml
├── configs/
├── baselines/
├── runs/
├── prompts/
├── src/soc_opt_agent/
└── tests/
```

### `configs/`

Runtime configuration files.

- [`campaign.yaml`](/home/cz2931/esp/soc_opt_agent/configs/campaign.yaml)
  - high-level campaign state
  - completed accelerators
  - recent improvements
- [`search_space.yaml`](/home/cz2931/esp/soc_opt_agent/configs/search_space.yaml)
  - accelerator order
  - SoC parameter allowlist
- [`scoring.yaml`](/home/cz2931/esp/soc_opt_agent/configs/scoring.yaml)
  - plateau window
  - minimum improvement
- [`llm.yaml`](/home/cz2931/esp/soc_opt_agent/configs/llm.yaml)
  - model name
  - response format
  - API key env var
  - API base

### `prompts/`

Prompt templates used by the LLM policy.

- [`system.txt`](/home/cz2931/esp/soc_opt_agent/prompts/system.txt)
- [`suggest_config.txt`](/home/cz2931/esp/soc_opt_agent/prompts/suggest_config.txt)
- [`reflect_on_result.txt`](/home/cz2931/esp/soc_opt_agent/prompts/reflect_on_result.txt)

### `baselines/`

Saved baseline artifacts, one directory per accelerator.

Example:

- [`summary.json`](/home/cz2931/esp/soc_opt_agent/baselines/aescipher_rtl/summary.json)
- [`metrics.json`](/home/cz2931/esp/soc_opt_agent/baselines/aescipher_rtl/metrics.json)
- [`config_before.esp_config`](/home/cz2931/esp/soc_opt_agent/baselines/aescipher_rtl/config_before.esp_config)
- [`config_after.esp_config`](/home/cz2931/esp/soc_opt_agent/baselines/aescipher_rtl/config_after.esp_config)
- [`transcript.txt`](/home/cz2931/esp/soc_opt_agent/baselines/aescipher_rtl/transcript.txt)

### `runs/`

Per-iteration candidate run artifacts.

Typical files:

- `proposal.json`
- `config_before.esp_config`
- `config_after.esp_config`
- `commands.json`
- `metrics.json`
- `summary.json`
- `transcript.txt`
- `agent_transcript.log`

### `src/soc_opt_agent/`

Main source tree.

#### Core entrypoints

- [`cli.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/cli.py)
  - `agentsoc` / `agentrtl` command-line interface
- [`paths.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/paths.py)
  - path helpers for SoC root, runs root, baselines root, transcript, and benchmark exe
- [`models.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/models.py)
  - typed models such as `IterationMetrics` and `LLMProposal`

#### Discovery

- [`discovery/accelerators.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/discovery/accelerators.py)
  - discovers accelerators under `accelerators/rtl`
  - skips `common`
  - sorts results

#### Config editing

- [`config_edit/parser.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/config_edit/parser.py)
  - parses `.esp_config`
- [`config_edit/editor.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/config_edit/editor.py)
  - applies safe SoC parameter changes
- [`config_edit/validators.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/config_edit/validators.py)
  - enforces allowlist and rejects unsafe edits

#### ESP flow

- [`esp_flow/commands.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/esp_flow/commands.py)
  - builds `make` commands
- [`esp_flow/executor.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/esp_flow/executor.py)
  - runs external commands
  - loads CAD tools env
  - strips virtualenv pollution before ESP commands
  - streams output into the agent transcript

#### LLM layer

- [`llm/client.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/llm/client.py)
  - Gemini API client
- [`llm/policy.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/llm/policy.py)
  - prompt assembly and proposal request
- [`llm/schemas.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/llm/schemas.py)
  - validates structured proposal output
- [`llm/prompts.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/llm/prompts.py)
  - safe prompt loading

#### Monitor and scoring

- [`monitor/transcript_parser.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/monitor/transcript_parser.py)
  - parses ESP monitor metrics from Modelsim transcript
- [`scoring/compare.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/scoring/compare.py)
  - computes improvement ratio
  - checks plateau

#### Orchestrator

- [`orchestrator/run_once.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/orchestrator/run_once.py)
  - baseline execution
  - candidate execution
  - artifact writing
- [`orchestrator/campaign_runner.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/orchestrator/campaign_runner.py)
  - `run_all` loop
  - status file
  - stop handling
- [`orchestrator/progress.py`](/home/cz2931/esp/soc_opt_agent/src/soc_opt_agent/orchestrator/progress.py)
  - agent-side transcript logging

### `tests/`

Pytest suite covering:

- discovery
- config editing
- transcript parsing
- scoring
- llm schema/client behavior
- executor environment handling
- baseline and candidate orchestration
- campaign loop control

## Files You Will Inspect Most Often

These are usually the most useful artifacts during debugging:

- global live agent log:
  - [`agent_transcript.log`](/home/cz2931/esp/soc_opt_agent/agent_transcript.log)
- active loop status:
  - [`run_all.status.json`](/home/cz2931/esp/soc_opt_agent/run_all.status.json)
- baseline result:
  - [`summary.json`](/home/cz2931/esp/soc_opt_agent/baselines/aescipher_rtl/summary.json)
- candidate proposal:
  - example [`proposal.json`](/home/cz2931/esp/soc_opt_agent/runs/run_20260406_235824_aescipher_rtl/proposal.json)
- candidate config diff inputs:
  - example [`config_before.esp_config`](/home/cz2931/esp/soc_opt_agent/runs/run_20260406_235824_aescipher_rtl/config_before.esp_config)
  - example [`config_after.esp_config`](/home/cz2931/esp/soc_opt_agent/runs/run_20260406_235824_aescipher_rtl/config_after.esp_config)
- Modelsim transcript:
  - [`transcript`](/home/cz2931/esp/socs/xilinx-vc707-xc7vx485t/modelsim/transcript)

## Current Search Space

The current allowlist for SoC tuning is:

- `CONFIG_QUEUE_SIZE`
- `CONFIG_COH_NOC_WIDTH`
- `CONFIG_DMA_NOC_WIDTH`
- `CONFIG_MEM_LINK_WIDTH`
- `CONFIG_CACHE_LINE_SIZE`
- `CONFIG_SLM_KBYTES`
- `CONFIG_CPU_CACHES`
- `CONFIG_ACC_CACHES`

The accelerator tile itself may also be changed manually when switching the target accelerator for baseline setup, but the agent does not perform general accelerator RTL editing.

## Current Baseline

The current saved `aescipher_rtl` baseline is:

- `passed: true`
- `accelerator_total_cycles: 63`
- `offchip_memory_accesses: 184`

Source:

- [`summary.json`](/home/cz2931/esp/soc_opt_agent/baselines/aescipher_rtl/summary.json)

## Logs and Status

### Agent transcript

`agent_transcript.log` is a workflow log, not just an LLM log.

It includes:

- stage transitions
- command start and end markers
- streamed output from `esp-config`, build, and sim
- failures
- final metrics summaries

Watch it with:

```bash
tail -f /home/cz2931/esp/soc_opt_agent/agent_transcript.log
```

### Modelsim transcript

The SoC and benchmark still write their usual simulation output to:

- [`transcript`](/home/cz2931/esp/socs/xilinx-vc707-xc7vx485t/modelsim/transcript)

That file contains:

- benchmark/application prints
- boot progress
- accelerator invocation prints
- final `ESP MONITOR STATS`

### Run-all status file

When `run_all` is active, it also writes:

- [`run_all.status.json`](/home/cz2931/esp/soc_opt_agent/run_all.status.json)

That file includes fields like:

- current accelerator
- phase
- baseline cycles
- best cycles
- recent improvements

## Environment Notes

The agent itself is intended to run from the project virtualenv, but ESP commands should not use the venv Python.

This project now sanitizes the child process environment before running ESP commands so that:

- `make esp-config` uses the system CAD environment
- `python3` resolves to the system interpreter expected by ESP tooling
- modules such as `Pmw` remain available

## Known Limitations

- no dedicated `comparison.json` yet for baseline vs each iteration
- `run_all.status.json` is useful but still fairly minimal
- no dedicated `llm_trace.json` with full prompts and raw responses
- `agentrtl` is only an alias, not a separate RTL optimization system
- the campaign loop is intentionally simple and currently uses plateau stopping

## Development

Run tests:

```bash
cd /home/cz2931/esp/soc_opt_agent
.venv/bin/pytest tests -q
```

Current expected result is all tests passing.

Reinstall editable entrypoints after changing `pyproject.toml` command scripts:

```bash
cd /home/cz2931/esp
/home/cz2931/esp/soc_opt_agent/.venv/bin/pip install -e /home/cz2931/esp/soc_opt_agent[dev]
```

## Recommended Commands

Most useful commands in practice:

```bash
cd /home/cz2931/esp/soc_opt_agent
source .venv/bin/activate
export GEMINI_API_KEY='your_key_here'
agentsoc status
agentsoc baseline
agentsoc run_once
agentsoc run_all
agentsoc stop
tail -f /home/cz2931/esp/soc_opt_agent/agent_transcript.log
```
